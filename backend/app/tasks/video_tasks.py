import asyncio
import logging
import time
import uuid

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.video_tasks.render_video",
    bind=True,
    max_retries=1,
    queue="video",
    time_limit=900,
)
def render_video(
    self,
    script_id: int,
    voice: str | None = None,
    image_provider: str | None = None,
) -> dict:
    """Full pipeline: audio → images → video → thumbnail."""
    import asyncio as _asyncio
    from app.models.script import Script, ScriptStatus
    from app.models.topic import Topic, TopicStatus
    from app.models.video import Video, VideoStatus
    from app.core import storage
    from app.core.config import settings
    from app.services.voice_generation.edge_tts_generator import EdgeTTSGenerator
    from app.services.image_generation.pexels_generator import get_image_generator
    from app.services.video_assembly.ffmpeg_assembler import FFmpegAssembler

    async def _run() -> dict:
        async with AsyncSessionLocal() as db:
            script = await db.get(Script, script_id)
            if not script:
                raise ValueError(f"Script {script_id} not found")

            video = Video(
                topic_id=script.topic_id,
                script_id=script_id,
                status=VideoStatus.GENERATING_AUDIO,
            )
            db.add(video)
            await db.commit()
            await db.refresh(video)

            start_time = time.time()
            run_id = uuid.uuid4().hex[:8]

            try:
                # --- Audio ---
                tts = EdgeTTSGenerator()
                audio_out = storage.audio_path(f"audio_{run_id}.mp3")
                full_text = f"{script.hook} {script.main_content} {script.cta}"
                voice_result = await tts.generate(
                    full_text,
                    audio_out,
                    voice or script.voice_style,
                )
                video.audio_path = voice_result.audio_path
                video.status = VideoStatus.GENERATING_IMAGES
                await db.commit()

                # --- Images ---
                scenes = script.scenes or []
                if not scenes:
                    scenes = [{"text": script.main_content, "image_prompt": script.title, "duration_seconds": 10.0}]

                img_gen = get_image_generator()
                image_paths: list[str] = []
                scene_durations: list[float] = []

                for i, scene in enumerate(scenes):
                    img_out = storage.image_path(f"img_{run_id}_{i:03d}.png")
                    prompt = scene.get("image_prompt", scene.get("text", script.title))
                    await img_gen.generate(
                        prompt,
                        img_out,
                        width=settings.default_video_width,
                        height=settings.default_video_height,
                    )
                    image_paths.append(img_out)
                    scene_durations.append(float(scene.get("duration_seconds", 5.0)))

                video.image_paths = image_paths
                video.status = VideoStatus.ASSEMBLING
                await db.commit()

                # --- Video assembly ---
                assembler = FFmpegAssembler()
                vid_out = storage.video_path(f"video_{run_id}.mp4")
                thumb_out = storage.thumbnail_path(f"thumb_{run_id}.jpg")

                asm_result = await assembler.assemble(
                    audio_path=voice_result.audio_path,
                    image_paths=image_paths,
                    output_path=vid_out,
                    thumbnail_path=thumb_out,
                    scene_durations=scene_durations,
                    width=settings.default_video_width,
                    height=settings.default_video_height,
                    fps=settings.default_video_fps,
                )

                # --- Finalize ---
                video.status = VideoStatus.RENDERED
                video.video_path = asm_result.video_path
                video.thumbnail_path = asm_result.thumbnail_path
                video.duration_seconds = asm_result.duration_seconds
                video.file_size_mb = asm_result.file_size_mb
                video.render_time_seconds = time.time() - start_time

                topic = await db.get(Topic, script.topic_id)
                if topic:
                    topic.status = TopicStatus.DONE

                await db.commit()
                return {"video_id": video.id, "video_path": asm_result.video_path}

            except Exception as exc:
                video.status = VideoStatus.FAILED
                video.error_message = str(exc)[:500]
                await db.commit()
                raise

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("render_video(script=%d) failed: %s", script_id, exc)
        raise self.retry(exc=exc, countdown=60)
