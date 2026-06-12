import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trend import Trend
from app.services.trend_discovery.base import DiscoveredTrend
from app.services.trend_discovery.reddit_discoverer import RedditDiscoverer
from app.services.trend_discovery.rss_discoverer import RSSDiscoverer

logger = logging.getLogger(__name__)

DEFAULT_NICHES = ["science", "history", "programming", "ai", "trivia"]


class TrendOrchestrator:
    def __init__(self) -> None:
        self.discoverers = [
            RSSDiscoverer(),
            RedditDiscoverer(),
        ]

    async def run(
        self,
        db: AsyncSession,
        niches: list[str] | None = None,
    ) -> list[Trend]:
        target_niches = niches or DEFAULT_NICHES
        all_trends: list[DiscoveredTrend] = []

        for discoverer in self.discoverers:
            try:
                found = await discoverer.discover(target_niches)
                all_trends.extend(found)
            except Exception as e:
                logger.error("Discoverer %s failed: %s", discoverer.name(), e)

        if not all_trends:
            logger.warning("No trends discovered")
            return []

        # Deduplicate by keyword (case-insensitive)
        seen: set[str] = set()
        unique: list[DiscoveredTrend] = []
        for t in sorted(all_trends, key=lambda x: x.score, reverse=True):
            key = t.keyword.lower()[:100]
            if key not in seen:
                seen.add(key)
                unique.append(t)

        orm_trends: list[Trend] = []
        for t in unique:
            trend = Trend(
                source=t.source,
                keyword=t.keyword,
                niche=t.niche,
                score=t.score,
                url=t.url,
                raw_data=t.raw_data,
            )
            db.add(trend)
            orm_trends.append(trend)

        await db.commit()
        logger.info("Saved %d unique trends to DB", len(orm_trends))
        return orm_trends
