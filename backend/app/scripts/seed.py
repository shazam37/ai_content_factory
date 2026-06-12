"""
Seed the database with starter topics for Science and History niches.
Run: docker compose exec api python -m app.scripts.seed
"""
import asyncio

from app.core.database import AsyncSessionLocal
from app.models.topic import Topic

SEED_TOPICS = [
    # Science
    {"title": "Why does time slow down near a black hole?", "niche": "science", "priority": 8},
    {"title": "The real reason humans lost their tails during evolution", "niche": "science", "priority": 7},
    {"title": "How your brain generates electricity to power your thoughts", "niche": "science", "priority": 7},
    {"title": "The experiment that proved quantum entanglement is real", "niche": "science", "priority": 9},
    {"title": "Why water is the strangest molecule on Earth", "niche": "science", "priority": 6},
    {"title": "The scale of the universe from quarks to galaxy clusters", "niche": "science", "priority": 8},
    {"title": "How CRISPR actually edits DNA inside living cells", "niche": "science", "priority": 9},
    {"title": "Why the placebo effect is far more powerful than we thought", "niche": "science", "priority": 7},
    # History
    {"title": "The forgotten city buried under Pompeii before the volcano", "niche": "history", "priority": 8},
    {"title": "Why the Library of Alexandria's destruction changed human history", "niche": "history", "priority": 9},
    {"title": "The plague that killed half of Rome in 165 AD", "niche": "history", "priority": 7},
    {"title": "How Genghis Khan connected East and West through trade", "niche": "history", "priority": 8},
    {"title": "The invention that accidentally created the modern world", "niche": "history", "priority": 7},
    {"title": "Why ancient Egyptians really built the pyramids", "niche": "history", "priority": 9},
    {"title": "The pirate republic that lasted 11 years in the Caribbean", "niche": "history", "priority": 8},
    {"title": "How the Silk Road shaped every civilization on Earth", "niche": "history", "priority": 7},
]


async def seed():
    async with AsyncSessionLocal() as db:
        for data in SEED_TOPICS:
            topic = Topic(**data)
            db.add(topic)
        await db.commit()
        print(f"Seeded {len(SEED_TOPICS)} topics")


if __name__ == "__main__":
    asyncio.run(seed())
