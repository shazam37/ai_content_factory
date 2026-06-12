import asyncio
import logging

import praw
import prawcore

from app.core.config import settings
from app.services.trend_discovery.base import BaseTrendDiscoverer, DiscoveredTrend

logger = logging.getLogger(__name__)

NICHE_SUBREDDITS: dict[str, list[str]] = {
    "science": ["science", "EverythingScience", "Physics", "chemistry", "biology"],
    "history": ["history", "HistoryMemes", "AskHistorians", "todayilearned"],
    "programming": ["programming", "Python", "MachineLearning", "artificial"],
    "ai": ["MachineLearning", "artificial", "singularity", "LocalLLaMA"],
    "trivia": ["todayilearned", "interestingasfuck", "Damnthatsinteresting"],
}


class RedditDiscoverer(BaseTrendDiscoverer):
    def __init__(self) -> None:
        self._reddit: praw.Reddit | None = None

    def _get_reddit(self) -> praw.Reddit | None:
        if not settings.reddit_client_id:
            return None
        if self._reddit is None:
            self._reddit = praw.Reddit(
                client_id=settings.reddit_client_id,
                client_secret=settings.reddit_client_secret,
                user_agent=settings.reddit_user_agent,
            )
        return self._reddit

    async def discover(self, niches: list[str]) -> list[DiscoveredTrend]:
        reddit = self._get_reddit()
        if reddit is None:
            logger.warning("Reddit credentials not configured — skipping Reddit discovery")
            return []

        trends: list[DiscoveredTrend] = []

        def _fetch_sync() -> list[DiscoveredTrend]:
            results: list[DiscoveredTrend] = []
            for niche in niches:
                subreddits = NICHE_SUBREDDITS.get(niche, [])
                for sub_name in subreddits[:2]:
                    try:
                        sub = reddit.subreddit(sub_name)
                        for post in sub.hot(limit=10):
                            if post.score < 100:
                                continue
                            results.append(
                                DiscoveredTrend(
                                    keyword=post.title,
                                    niche=niche,
                                    source="reddit",
                                    score=min(post.score / 10000, 1.0),
                                    url=f"https://reddit.com{post.permalink}",
                                    raw_data={
                                        "subreddit": sub_name,
                                        "score": post.score,
                                        "num_comments": post.num_comments,
                                        "upvote_ratio": post.upvote_ratio,
                                    },
                                )
                            )
                    except prawcore.exceptions.PrawcoreException as e:
                        logger.warning("Reddit error for r/%s: %s", sub_name, e)
            return results

        trends = await asyncio.to_thread(_fetch_sync)
        logger.info("Reddit: discovered %d trends", len(trends))
        return trends
