import logging

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.generation_tasks.generate_script",
    bind=True,
    max_retries=2,
    queue="generation",
)
def generate_script(self, topic_id: int, voice: str | None = None) -> dict:
    """Generate a script for a topic, score it, and save to DB."""
    import asyncio
    from sqlalchemy import select

    from app.models.topic import Topic, TopicStatus
    from app.models.script import Script, ScriptStatus
    from app.services.script_generation.ollama_generator import OllamaScriptGenerator
    from app.services.script_generation.quality_scorer import QualityScorer
    from app.core.config import settings

    async def _run() -> dict:
        async with AsyncSessionLocal() as db:
            topic = await db.get(Topic, topic_id)
            if not topic:
                raise ValueError(f"Topic {topic_id} not found")

            topic.status = TopicStatus.GENERATING
            await db.commit()

            generator = OllamaScriptGenerator()
            scorer = QualityScorer()

            generated = await generator.generate(topic.title, topic.niche)
            score, feedback = await scorer.score(generated)

            script = Script(
                topic_id=topic_id,
                hook=generated.hook,
                main_content=generated.main_content,
                cta=generated.cta,
                scenes=[s if isinstance(s, dict) else vars(s) for s in generated.scenes],
                title=generated.title,
                description=generated.description,
                hashtags=generated.hashtags,
                quality_score=score,
                quality_feedback=feedback,
                model_used=generated.model_used,
                voice_style=voice or settings.voice_default,
                estimated_duration_seconds=generated.estimated_duration_seconds,
                status=ScriptStatus.APPROVED if scorer.passes_threshold(score) else ScriptStatus.DRAFT,
            )
            db.add(script)

            topic.status = TopicStatus.SELECTED if scorer.passes_threshold(score) else TopicStatus.PENDING
            await db.commit()
            await db.refresh(script)

            return {"script_id": script.id, "quality_score": score, "status": script.status}

    try:
        import asyncio
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("generate_script(%d) failed: %s", topic_id, exc)
        raise self.retry(exc=exc, countdown=30)
