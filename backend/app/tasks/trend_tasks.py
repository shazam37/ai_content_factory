import logging

from celery import shared_task

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.trend_tasks.discover_trends", bind=True, max_retries=3)
def discover_trends(self, niches: list[str] | None = None) -> dict:
    """Discover trends from all configured sources and save to DB."""
    import asyncio
    from app.services.trend_discovery.orchestrator import TrendOrchestrator

    async def _run():
        async with AsyncSessionLocal() as db:
            orchestrator = TrendOrchestrator()
            trends = await orchestrator.run(db, niches)
            return len(trends)

    try:
        count = asyncio.run(_run())
        logger.info("discover_trends: saved %d trends", count)
        return {"status": "ok", "trends_saved": count}
    except Exception as exc:
        logger.error("discover_trends failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)
