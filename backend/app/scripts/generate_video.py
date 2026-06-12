"""
Generate a complete video for a given topic ID.
Run: docker compose exec api python -m app.scripts.generate_video --topic-id 1

This is a synchronous end-to-end runner useful for local testing outside Celery.
"""
import argparse
import asyncio
import sys
import time

from app.core.database import AsyncSessionLocal
from app.core.config import settings
from app.core import storage
from app.models.topic import Topic, TopicStatus
from app.models.script import Script, ScriptStatus
from app.models.video import Video, VideoStatus
from app.services.script_generation.ollama_generator import OllamaScriptGenerator
from app.services.script_generation.quality_scorer import QualityScorer
from app.services.voice_generation.edge_tts_generator import EdgeTTSGenerator
from app.services.image_generation.pexels_generator import get_image_generator
from app.services.video_assembly.ffmpeg_assembler import FFmpegAssembler
import uuid


async def run(topic_id: int, voice: str | None = None) -> None:
    async with AsyncSessionLocal() as db:
        topic = await db.get(Topic, topic_id)
        if not topic:
            print(f"Topic {topic_id} not found", file=sys.stderr)
            sys.exit(1)

        print(f"\n[1/5] Generating script for: {topic.title}")
        gen = OllamaScriptGenerator()
        scorer = QualityScorer()
        script_data = await gen.generate(topic.title, topic.niche)
        score, feedback = await scorer.score(script_data)
        print(f"      Quality score: {score:.1f}/10")

        script = Script(
            topic_id=topic_id,
            hook=script_data.hook,
            main_content=script_data.main_content,
            cta=script_data.cta,
            scenes=[s if isinstance(s, dict) else vars(s) for s in script_data.scenes],
            title=script_data.title,
            description=script_data.description,
            hashtags=script_data.hashtags,
            quality_score=score,
            quality_feedback=feedback,
            model_used=script_data.model_used,
            voice_style=voice or settings.voice_default,
            estimated_duration_seconds=script_data.estimated_duration_seconds,
            status=ScriptStatus.APPROVED,
        )
        db.add(script)
        topic.status = TopicStatus.GENERATING
        await db.commit()
        await db.refresh(script)

        print(f"\n[2/5] Generating voiceover...")
        run_id = uuid.uuid4().hex[:8]
        tts = EdgeTTSGenerator()
        audio_out = storage.audio_path(f"audio_{run_id}.mp3")
        full_text = f"{script.hook} {script.main_content} {script.cta}"
        voice_result = await tts.generate(full_text, audio_out, voice)
        print(f"      Audio: {voice_result.duration_seconds:.1f}s -> {audio_out}")

        print(f"\n[3/5] Generating {len(script.scenes or [])} scene images...")
        img_gen = get_image_generator()
        image_paths: list[str] = []
        scene_durations: list[float] = []
        scenes = script.scenes or [{"text": script.main_content, "image_prompt": script.title, "duration_seconds": 10.0}]

        for i, scene in enumerate(scenes):
            img_out = storage.image_path(f"img_{run_id}_{i:03d}.png")
            prompt = scene.get("image_prompt", scene.get("text", script.title))
            print(f"      Scene {i+1}: {prompt[:60]}")
            await img_gen.generate(prompt, img_out, settings.default_video_width, settings.default_video_height)
            image_paths.append(img_out)
            scene_durations.append(float(scene.get("duration_seconds", 5.0)))

        print(f"\n[4/5] Assembling video...")
        assembler = FFmpegAssembler()
        vid_out = storage.video_path(f"video_{run_id}.mp4")
        thumb_out = storage.thumbnail_path(f"thumb_{run_id}.jpg")
        start = time.time()
        result = await assembler.assemble(
            audio_path=voice_result.audio_path,
            image_paths=image_paths,
            output_path=vid_out,
            thumbnail_path=thumb_out,
            scene_durations=scene_durations,
            width=settings.default_video_width,
            height=settings.default_video_height,
        )
        render_time = time.time() - start

        video = Video(
            topic_id=topic_id,
            script_id=script.id,
            status=VideoStatus.RENDERED,
            audio_path=voice_result.audio_path,
            image_paths=image_paths,
            video_path=result.video_path,
            thumbnail_path=result.thumbnail_path,
            duration_seconds=result.duration_seconds,
            file_size_mb=result.file_size_mb,
            render_time_seconds=render_time,
        )
        db.add(video)
        topic.status = TopicStatus.DONE
        await db.commit()

        print(f"\n[5/5] Done!")
        print(f"      Video:     {result.video_path}")
        print(f"      Thumbnail: {result.thumbnail_path}")
        print(f"      Duration:  {result.duration_seconds:.1f}s")
        print(f"      Size:      {result.file_size_mb:.1f} MB")
        print(f"      Render:    {render_time:.0f}s")
        print(f"\n      Title: {script.title}")
        print(f"      Tags:  {' '.join(['#' + t for t in (script.hashtags or [])])}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic-id", type=int, required=True)
    parser.add_argument("--voice", type=str, default=None)
    args = parser.parse_args()
    asyncio.run(run(args.topic_id, args.voice))
