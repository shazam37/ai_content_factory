import asyncio
import logging

import feedparser

from app.services.trend_discovery.base import BaseTrendDiscoverer, DiscoveredTrend

logger = logging.getLogger(__name__)

NICHE_FEEDS: dict[str, list[tuple[str, str]]] = {
    "science": [
        ("https://feeds.bbci.co.uk/news/science_and_environment/rss.xml", "BBC Science"),
        ("https://www.sciencedaily.com/rss/top/science.xml", "ScienceDaily"),
        ("https://rss.nytimes.com/services/xml/rss/nyt/Science.xml", "NYT Science"),
    ],
    "history": [
        ("https://feeds.bbci.co.uk/news/world/rss.xml", "BBC World"),
        ("https://www.history.com/.rss/full/", "History Channel"),
    ],
    "programming": [
        ("https://hnrss.org/frontpage", "Hacker News"),
        ("https://dev.to/feed", "Dev.to"),
    ],
    "ai": [
        ("https://hnrss.org/frontpage?q=AI+machine+learning", "HN AI"),
        ("https://feeds.feedburner.com/venturebeat/SZYF", "VentureBeat AI"),
    ],
    "trivia": [
        ("https://feeds.feedburner.com/MentalFloss", "Mental Floss"),
    ],
}


class RSSDiscoverer(BaseTrendDiscoverer):
    async def discover(self, niches: list[str]) -> list[DiscoveredTrend]:
        trends: list[DiscoveredTrend] = []

        def _parse_feed(url: str, source_name: str, niche: str) -> list[DiscoveredTrend]:
            results: list[DiscoveredTrend] = []
            try:
                feed = feedparser.parse(url)
                for i, entry in enumerate(feed.entries[:8]):
                    title = entry.get("title", "").strip()
                    if not title or len(title) < 10:
                        continue
                    score = max(0.0, 1.0 - (i * 0.1))
                    results.append(
                        DiscoveredTrend(
                            keyword=title,
                            niche=niche,
                            source="rss",
                            score=score,
                            url=entry.get("link"),
                            raw_data={
                                "feed": source_name,
                                "summary": entry.get("summary", "")[:300],
                                "published": entry.get("published", ""),
                            },
                        )
                    )
            except Exception as e:
                logger.warning("RSS parse error for %s: %s", url, e)
            return results

        for niche in niches:
            feeds = NICHE_FEEDS.get(niche, [])
            fetch_tasks = [
                asyncio.to_thread(_parse_feed, url, name, niche)
                for url, name in feeds
            ]
            results_per_feed = await asyncio.gather(*fetch_tasks, return_exceptions=True)
            for result in results_per_feed:
                if isinstance(result, list):
                    trends.extend(result)

        logger.info("RSS: discovered %d trends", len(trends))
        return trends
