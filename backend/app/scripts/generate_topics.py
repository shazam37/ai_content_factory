"""
LLM-powered topic generator. Creates new unique topics and seeds them into the DB.
Queries existing topics to avoid duplicates.

Usage:
  # Generate 20 new science topics
  docker compose exec api python -m app.scripts.generate_topics --niche science --count 20

  # Generate for every configured niche
  docker compose exec api python -m app.scripts.generate_topics --all-niches --count 15

  # Dry-run: print without saving
  docker compose exec api python -m app.scripts.generate_topics --niche history --count 10 --dry-run

  # List all existing topics
  docker compose exec api python -m app.scripts.generate_topics --list
"""
import argparse
import asyncio
import json
import sys
from typing import Any

from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.topic import Topic, TopicStatus
from app.services.llm.factory import get_llm_client

_ALL_NICHES = ["science", "history", "programming", "ai", "trivia"]

_SYSTEM = (
    "You are a viral YouTube Shorts content strategist. "
    "Your job is to generate fresh, unique, mind-blowing educational topic ideas "
    "for 60-second short-form videos. "
    "Each topic must make the viewer think: 'I never knew that!' or 'Wait, seriously?'. "
    "Output ONLY valid JSON — no markdown, no extra text."
)


def _build_prompt(niche: str, existing: list[str], count: int) -> str:
    existing_block = "\n".join(f"  - {t}" for t in existing[:120])
    return f"""Generate exactly {count} unique YouTube Shorts topic ideas for the "{niche}" niche.

ALREADY-MADE TOPICS — do NOT create anything similar to these:
{existing_block or "  (none yet)"}

REQUIREMENTS:
- Every topic must be conceptually distinct from all existing ones
- Mix complexity: some quick surprising facts (complexity 1-2) and some deep dives (4-5)
- Mix eras: ancient, historical, modern, cutting-edge, speculative future
- Mix scale: subatomic → galactic, micro-organism → civilisation
- Be specific and concrete ("Why do neutron stars spin 700 times per second?" not "Cool space facts")
- Must have strong viral hook potential — surprising, counterintuitive, or emotionally compelling
- For "science": physics, biology, chemistry, neuroscience, astronomy, geology, etc.
- For "history": battles, inventions, forgotten civilisations, turning points, figures
- For "programming": algorithms, language history, legendary bugs, architectural decisions
- For "ai": breakthroughs, failures, ethics, capabilities, future implications
- For "trivia": strange laws, animal facts, record-breaking feats, weird coincidences

Return JSON with this exact schema:
{{
  "topics": [
    {{
      "title": "Specific catchy title under 80 characters",
      "description": "2–3 sentences covering what the video explains and why it's mind-blowing",
      "complexity": <integer 1–5>
    }}
  ]
}}"""


async def _fetch_existing_titles(niche: str | None = None) -> list[str]:
    async with AsyncSessionLocal() as db:
        stmt = select(Topic.title)
        if niche:
            stmt = stmt.where(Topic.niche == niche)
        result = await db.execute(stmt)
        return [row[0] for row in result.all()]


async def _generate_for_niche(niche: str, count: int, dry_run: bool) -> int:
    existing = await _fetch_existing_titles(niche)
    llm = get_llm_client(settings)

    # Generate in batches of 8 — LLM quality degrades for larger batches
    batch = 8
    total_added = 0
    remaining = count

    while remaining > 0:
        this_batch = min(batch, remaining)
        prompt = _build_prompt(niche, existing, this_batch)

        try:
            raw = await llm.complete(
                _SYSTEM, prompt,
                temperature=1.0,   # high temp = more variety
                max_tokens=4096,
                json_mode=True,
            )
            data = json.loads(raw)
            new_topics: list[dict[str, Any]] = data.get("topics", [])
        except Exception as exc:
            print(f"  [!] LLM call failed: {exc}", file=sys.stderr)
            break

        if not new_topics:
            print(f"  [!] LLM returned empty topics list", file=sys.stderr)
            break

        if dry_run:
            for t in new_topics:
                cmx = t.get("complexity", "?")
                print(f"  [{cmx}/5] {t.get('title', '?')}")
                if t.get("description"):
                    print(f"         {t['description'][:100]}")
            total_added += len(new_topics)
        else:
            async with AsyncSessionLocal() as db:
                added_this_batch = 0
                for t in new_topics:
                    title = (t.get("title") or "").strip()
                    if not title:
                        continue
                    # Skip near-duplicates (case-insensitive exact match)
                    if title.lower() in {e.lower() for e in existing}:
                        print(f"  [skip] Duplicate: {title[:70]}")
                        continue
                    topic = Topic(
                        title=title,
                        description=(t.get("description") or "")[:500],
                        niche=niche,
                        status=TopicStatus.PENDING,
                        priority=5,
                    )
                    db.add(topic)
                    existing.append(title)  # prevent dups within same batch run
                    added_this_batch += 1
                await db.commit()
            total_added += added_this_batch
            print(f"  + {added_this_batch} topics added (batch)")

        remaining -= len(new_topics)

    return total_added


async def _list_topics() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Topic).order_by(Topic.niche, Topic.id))
        topics = result.scalars().all()

    if not topics:
        print("No topics in DB yet.")
        return

    current_niche = None
    for t in topics:
        if t.niche != current_niche:
            current_niche = t.niche
            print(f"\n── {current_niche.upper()} ─────────────────")
        status_tag = f"[{t.status}]"
        print(f"  {t.id:4d} {status_tag:12s} {t.title}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Generate unique topics using LLM")
    parser.add_argument("--niche", choices=_ALL_NICHES, help="Target niche")
    parser.add_argument("--all-niches", action="store_true", help="Generate for all niches")
    parser.add_argument("--count", type=int, default=10, help="Topics to generate per niche")
    parser.add_argument("--dry-run", action="store_true", help="Print topics without saving")
    parser.add_argument("--list", action="store_true", help="List all existing topics")
    args = parser.parse_args()

    if args.list:
        await _list_topics()
        return

    niches = _ALL_NICHES if args.all_niches else ([args.niche] if args.niche else None)
    if not niches:
        parser.error("Specify --niche or --all-niches")

    for niche in niches:
        label = "DRY RUN — " if args.dry_run else ""
        print(f"\n{label}Generating {args.count} topics for niche: {niche}")
        added = await _generate_for_niche(niche, args.count, args.dry_run)
        action = "Would add" if args.dry_run else "Added"
        print(f"  {action} {added} topics for '{niche}'")


if __name__ == "__main__":
    asyncio.run(main())
