import logging

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

_REPLENISH_THRESHOLD = 5   # generate new topics when fewer than this many are pending
_REPLENISH_COUNT = 10      # how many new topics to generate per niche when low


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
    from app.services.llm.factory import get_llm_client, get_quality_client
    from app.services.script_generation.llm_generator import LLMScriptGenerator
    from app.services.script_generation.quality_scorer import QualityScorer
    from app.core.config import settings

    async def _run() -> dict:
        async with AsyncSessionLocal() as db:
            topic = await db.get(Topic, topic_id)
            if not topic:
                raise ValueError(f"Topic {topic_id} not found")

            topic.status = TopicStatus.GENERATING
            await db.commit()

            generator = LLMScriptGenerator(get_llm_client(settings))
            scorer = QualityScorer(get_quality_client(settings))

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


@celery_app.task(
    name="app.tasks.generation_tasks.replenish_topics",
    bind=True,
    max_retries=1,
    queue="generation",
)
def replenish_topics(self) -> dict:
    """
    Check each niche. If pending topic count < threshold, use LLM to generate
    new unique topics so the queue never runs dry.
    Runs on a schedule (see celery_app.py beat_schedule).
    """
    import asyncio
    from sqlalchemy import select, func
    from app.models.topic import Topic, TopicStatus
    from app.core.config import settings
    from app.services.llm.factory import get_llm_client
    import json

    _NICHES = ["science", "history", "programming", "ai", "trivia"]

    _SYSTEM = (
        "You are a viral YouTube Shorts content strategist. "
        "Generate unique, mind-blowing educational topic ideas for 60-second videos. "
        "Output ONLY valid JSON."
    )

    async def _run() -> dict:
        results = {}
        async with AsyncSessionLocal() as db:
            for niche in _NICHES:
                # Count pending
                count_q = await db.execute(
                    select(func.count(Topic.id))
                    .where(Topic.niche == niche, Topic.status == TopicStatus.PENDING)
                )
                pending = count_q.scalar() or 0

                if pending >= _REPLENISH_THRESHOLD:
                    results[niche] = {"pending": pending, "added": 0}
                    continue

                # Get existing titles for deduplication
                titles_q = await db.execute(select(Topic.title).where(Topic.niche == niche))
                existing = [r[0] for r in titles_q.all()]

                need = _REPLENISH_COUNT
                existing_block = "\n".join(f"  - {t}" for t in existing[:100])
                prompt = (
                    f'Generate exactly {need} unique YouTube Shorts topics for "{niche}".\n'
                    f"EXISTING TOPICS (do NOT repeat):\n{existing_block or '  (none)'}\n"
                    f"Return JSON: {{\"topics\": [{{\"title\": \"...\", \"description\": \"...\", \"complexity\": 1-5}}]}}"
                )

                try:
                    llm = get_llm_client(settings)
                    raw = await llm.complete(_SYSTEM, prompt, temperature=1.0, max_tokens=3000, json_mode=True)
                    data = json.loads(raw)
                    new_topics = data.get("topics", [])
                except Exception as exc:
                    logger.warning("replenish_topics LLM call failed for %s: %s", niche, exc)
                    results[niche] = {"pending": pending, "added": 0, "error": str(exc)}
                    continue

                added = 0
                existing_lower = {e.lower() for e in existing}
                for t in new_topics:
                    title = (t.get("title") or "").strip()
                    if not title or title.lower() in existing_lower:
                        continue
                    db.add(Topic(
                        title=title,
                        description=(t.get("description") or "")[:500],
                        niche=niche,
                        status=TopicStatus.PENDING,
                        priority=5,
                    ))
                    existing_lower.add(title.lower())
                    added += 1

                await db.commit()
                results[niche] = {"pending": pending, "added": added}
                logger.info("replenish_topics: %s — added %d topics (was %d pending)", niche, added, pending)

        return results

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("replenish_topics failed: %s", exc)
        raise self.retry(exc=exc, countdown=120)
