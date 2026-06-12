"""
Run trend discovery manually and print results.
Run: docker compose exec api python -m app.scripts.run_discovery
"""
import asyncio

from app.core.database import AsyncSessionLocal
from app.services.trend_discovery.orchestrator import TrendOrchestrator


async def main():
    async with AsyncSessionLocal() as db:
        orchestrator = TrendOrchestrator()
        trends = await orchestrator.run(db)
        print(f"\nDiscovered {len(trends)} trends:\n")
        for t in trends[:20]:
            print(f"  [{t.niche:12s}] ({t.score:.2f}) {t.keyword[:80]}")


if __name__ == "__main__":
    asyncio.run(main())
