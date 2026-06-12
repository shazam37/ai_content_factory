"""
FFmpeg-based video assembler.

Pipeline:
1. Probe audio duration.
2. Scale scene durations to match actual audio length.
3. Per scene: scale → Ken Burns zoom/pan → fade in/out → encode clip.
4. Concatenate clips (simple copy concat — fades create smooth transitions).
5. Mix narration + ambient background music.
6. Mux video + mixed audio → final MP4.
7. Extract thumbnail.
"""
import asyncio
import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path

from app.core import storage
from app.services.video_assembly.base import BaseVideoAssembler, VideoAssemblyResult

logger = logging.getLogger(__name__)

_FADE_DURATION = 0.35   # seconds — fade out / fade in on each clip (creates crossfade feel)
_BGM_VOLUME = 0.18      # background music volume relative to narration (1.0)


def _ffprobe_duration(path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", path],
        capture_output=True, text=True, timeout=15,
    )
    data = json.loads(result.stdout)
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "audio":
            return float(stream.get("duration", 0))
    return 0.0


def _build_ken_burns_filter(duration: float, w: int, h: int, idx: int) -> str:
    """
    Four alternating Ken Burns patterns to keep visual interest:
      0 → slow zoom-in from centre
      1 → pan left-to-right at fixed zoom
      2 → slow zoom-in anchored top-left
      3 → pan right-to-left at fixed zoom
    The zoompan filter operates on the 2× up-scaled image (w*2, h*2).
    """
    fps = 30
    nb = int(duration * fps)
    ze = 1.08          # zoom-end (8% magnification)
    sw = w * 2         # scaled width fed to zoompan
    sh = h * 2
    # Maximum pixel displacement at ze in the 2× image
    mx = sw * (1.0 - 1.0 / ze)   # ≈ 160 for 1080p
    my = sh * (1.0 - 1.0 / ze)   # ≈ 284 for 1920p

    mode = idx % 4
    if mode == 0:
        # Slow zoom from centre
        return (
            f"zoompan=z='min(zoom+0.0007,{ze})'"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={nb}:s={w}x{h}:fps={fps}"
        )
    elif mode == 1:
        # Pan left → right, fixed zoom
        spd = mx / nb
        return (
            f"zoompan=z='{ze}'"
            f":x='min({mx:.1f},on*{spd:.5f})':y='{my/2:.1f}'"
            f":d={nb}:s={w}x{h}:fps={fps}"
        )
    elif mode == 2:
        # Slow zoom anchored top-left
        return (
            f"zoompan=z='min(zoom+0.0007,{ze})'"
            f":x='0':y='0'"
            f":d={nb}:s={w}x{h}:fps={fps}"
        )
    else:
        # Pan right → left, fixed zoom
        spd = mx / nb
        return (
            f"zoompan=z='{ze}'"
            f":x='max(0,{mx:.1f}-on*{spd:.5f})':y='{my/2:.1f}'"
            f":d={nb}:s={w}x{h}:fps={fps}"
        )


def _assemble_sync(
    audio_path: str,
    image_paths: list[str],
    output_path: str,
    thumbnail_path: str,
    scene_durations: list[float],
    width: int,
    height: int,
    fps: int,
    bg_music_path: str | None,
    total_duration: float,
) -> VideoAssemblyResult:
    n = len(image_paths)
    fd = _FADE_DURATION

    with tempfile.TemporaryDirectory() as tmpdir:
        clip_paths: list[str] = []

        # ── Encode each scene clip ────────────────────────────────────────────
        for i, (img, dur) in enumerate(zip(image_paths, scene_durations)):
            clip_out = os.path.join(tmpdir, f"clip_{i:03d}.mp4")
            zoompan = _build_ken_burns_filter(dur, width, height, i)

            # fade_out_start must not exceed (dur - fd - 0.05) to avoid negatives
            fade_out_st = max(0.0, dur - fd - 0.05)

            vf = (
                f"scale={width * 2}:{height * 2},"
                f"crop={width * 2}:{height * 2},"
                f"{zoompan},"
                f"scale={width}:{height}:flags=lanczos,"
                f"fade=t=in:st=0:d={fd},"
                f"fade=t=out:st={fade_out_st:.3f}:d={fd}"
            )

            cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-i", img,
                "-t", str(dur),
                "-vf", vf,
                "-c:v", "libx264", "-preset", "ultrafast",
                "-pix_fmt", "yuv420p", "-r", str(fps),
                clip_out,
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode != 0:
                logger.error("Clip %d encode failed: %s", i, result.stderr.decode()[:500])
                raise RuntimeError(f"FFmpeg failed on clip {i}")
            clip_paths.append(clip_out)

        # ── Concatenate clips ─────────────────────────────────────────────────
        concat_file = os.path.join(tmpdir, "concat.txt")
        with open(concat_file, "w") as f:
            for cp in clip_paths:
                f.write(f"file '{cp}'\n")

        concat_out = os.path.join(tmpdir, "concat.mp4")
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
             "-i", concat_file, "-c", "copy", concat_out],
            capture_output=True, timeout=120, check=True,
        )

        # ── Mix audio: narration + optional background music ──────────────────
        if bg_music_path and os.path.exists(bg_music_path):
            fade_out_st = max(0.0, total_duration - 4.0)
            filter_audio = (
                f"[1:a]volume=1.0[narr];"
                f"[2:a]volume={_BGM_VOLUME},"
                f"atrim=end={total_duration + 5:.1f},"
                f"afade=t=in:st=0:d=3,"
                f"afade=t=out:st={fade_out_st:.1f}:d=4[bgm];"
                f"[narr][bgm]amix=inputs=2:duration=first:dropout_transition=0[aout]"
            )
            mix_cmd = [
                "ffmpeg", "-y",
                "-i", concat_out,
                "-i", audio_path,
                "-i", bg_music_path,
                "-filter_complex", filter_audio,
                "-map", "0:v:0", "-map", "[aout]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart",
                output_path,
            ]
        else:
            # No music — plain narration mux
            mix_cmd = [
                "ffmpeg", "-y",
                "-i", concat_out, "-i", audio_path,
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-shortest", "-movflags", "+faststart",
                output_path,
            ]

        result = subprocess.run(mix_cmd, capture_output=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg mux failed: {result.stderr.decode()[:500]}")

    # ── Thumbnail ─────────────────────────────────────────────────────────────
    subprocess.run(
        ["ffmpeg", "-y", "-i", output_path,
         "-vframes", "1", "-q:v", "2", thumbnail_path],
        capture_output=True, timeout=30,
    )

    file_size = storage.file_size_mb(output_path)
    actual_duration = _ffprobe_duration(output_path) or total_duration

    return VideoAssemblyResult(
        video_path=output_path,
        thumbnail_path=thumbnail_path,
        duration_seconds=actual_duration,
        file_size_mb=file_size,
    )


class FFmpegAssembler(BaseVideoAssembler):
    async def assemble(
        self,
        audio_path: str,
        image_paths: list[str],
        output_path: str,
        thumbnail_path: str,
        scene_durations: list[float] | None = None,
        width: int = 1080,
        height: int = 1920,
        fps: int = 30,
        niche: str = "science",
        topic_id: int = 0,
        topic_title: str = "",
    ) -> VideoAssemblyResult:
        if not image_paths:
            raise ValueError("No images provided")

        # Probe actual audio duration and scale scene durations to match
        audio_duration = _ffprobe_duration(audio_path) or 45.0

        if scene_durations is None or len(scene_durations) != len(image_paths):
            per_scene = audio_duration / len(image_paths)
            scene_durations = [per_scene] * len(image_paths)
        else:
            total = sum(scene_durations)
            if total > 0:
                scale = audio_duration / total
                scene_durations = [d * scale for d in scene_durations]

        total_duration = sum(scene_durations)

        logger.info(
            "Assembling: %d scenes, %.1fs, %dx%d, niche=%s",
            len(image_paths), total_duration, width, height, niche,
        )

        # Generate (or retrieve cached) background music — unique per topic
        from app.services.video_assembly.music_generator import get_background_music
        bg_music_path = await get_background_music(
            total_duration, topic_id, topic_title or niche, niche
        )
        if bg_music_path:
            logger.info("Background music: %s", bg_music_path)
        else:
            logger.warning("No background music available — continuing without")

        result = await asyncio.to_thread(
            _assemble_sync,
            audio_path,
            image_paths,
            output_path,
            thumbnail_path,
            scene_durations,
            width,
            height,
            fps,
            bg_music_path,
            total_duration,
        )

        logger.info(
            "Video ready: %s (%.1fs, %.1fMB)",
            result.video_path, result.duration_seconds, result.file_size_mb,
        )
        return result
