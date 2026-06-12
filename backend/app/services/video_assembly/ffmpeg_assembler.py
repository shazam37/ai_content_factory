"""
FFmpeg-based video assembler.

Strategy:
1. Get total audio duration via ffprobe.
2. Distribute that duration across scenes (proportional to scene text length,
   or equal if scene_durations not provided).
3. For each scene image: scale + pad to target resolution, apply Ken Burns effect.
4. Concatenate all scene clips.
5. Overlay the audio track.
6. Extract first frame as thumbnail.
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


def _build_ken_burns_filter(img_path: str, duration: float, w: int, h: int, idx: int) -> str:
    """Zoompan filter: slow zoom-in or pan depending on scene index."""
    zoom_start = 1.0
    zoom_end = 1.08
    fps = 30
    nb_frames = int(duration * fps)

    if idx % 2 == 0:
        # Zoom in from center
        zoompan = (
            f"zoompan=z='min(zoom+0.0008,{zoom_end})':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={nb_frames}:s={w}x{h}:fps={fps}"
        )
    else:
        # Slow pan from left
        zoompan = (
            f"zoompan=z='{zoom_end}':x='x+0.5':y='ih/2-(ih/zoom/2)'"
            f":d={nb_frames}:s={w}x{h}:fps={fps}"
        )
    return zoompan


def _assemble_sync(
    audio_path: str,
    image_paths: list[str],
    output_path: str,
    thumbnail_path: str,
    scene_durations: list[float],
    width: int,
    height: int,
    fps: int,
) -> VideoAssemblyResult:
    total_duration = sum(scene_durations)
    n = len(image_paths)

    with tempfile.TemporaryDirectory() as tmpdir:
        clip_paths: list[str] = []

        for i, (img, dur) in enumerate(zip(image_paths, scene_durations)):
            clip_out = os.path.join(tmpdir, f"clip_{i:03d}.mp4")
            zoompan = _build_ken_burns_filter(img, dur, width, height, i)

            cmd = [
                "ffmpeg", "-y",
                "-loop", "1",
                "-i", img,
                "-t", str(dur),
                "-vf",
                (
                    f"scale={width*2}:{height*2},"
                    f"crop={width*2}:{height*2},"
                    f"{zoompan},"
                    f"scale={width}:{height}:flags=lanczos"
                ),
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-pix_fmt", "yuv420p",
                "-r", str(fps),
                clip_out,
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode != 0:
                logger.error("FFmpeg clip %d failed: %s", i, result.stderr.decode()[:500])
                raise RuntimeError(f"FFmpeg failed on clip {i}")
            clip_paths.append(clip_out)

        # Write concat list
        concat_file = os.path.join(tmpdir, "concat.txt")
        with open(concat_file, "w") as f:
            for cp in clip_paths:
                f.write(f"file '{cp}'\n")

        # Concatenate clips
        concat_out = os.path.join(tmpdir, "concat.mp4")
        concat_cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", concat_file,
            "-c", "copy",
            concat_out,
        ]
        subprocess.run(concat_cmd, capture_output=True, timeout=120, check=True)

        # Mix with audio
        mix_cmd = [
            "ffmpeg", "-y",
            "-i", concat_out,
            "-i", audio_path,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            "-movflags", "+faststart",
            output_path,
        ]
        result = subprocess.run(mix_cmd, capture_output=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg mux failed: {result.stderr.decode()[:500]}")

    # Extract thumbnail from first frame
    thumb_cmd = [
        "ffmpeg", "-y",
        "-i", output_path,
        "-vframes", "1",
        "-q:v", "2",
        thumbnail_path,
    ]
    subprocess.run(thumb_cmd, capture_output=True, timeout=30)

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
    ) -> VideoAssemblyResult:
        if not image_paths:
            raise ValueError("No images provided for video assembly")

        # Resolve scene durations
        audio_duration = _ffprobe_duration(audio_path)
        if audio_duration == 0:
            audio_duration = 45.0  # fallback

        if scene_durations is None or len(scene_durations) != len(image_paths):
            per_scene = audio_duration / len(image_paths)
            scene_durations = [per_scene] * len(image_paths)
        else:
            # Scale durations to match actual audio
            total = sum(scene_durations)
            if total > 0:
                scale = audio_duration / total
                scene_durations = [d * scale for d in scene_durations]

        logger.info(
            "Assembling video: %d scenes, %.1fs audio, %dx%d",
            len(image_paths), audio_duration, width, height,
        )

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
        )

        logger.info("Video ready: %s (%.1fs, %.1fMB)", result.video_path, result.duration_seconds, result.file_size_mb)
        return result
