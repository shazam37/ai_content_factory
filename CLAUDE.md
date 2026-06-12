# AI Content Factory — CLAUDE.md

This file gives a coding agent everything needed to understand the project, what has been built, and how to continue. Read it fully before making any changes.

---

## Project Vision

Build a fully automated, scalable AI-powered platform that produces short-form video content for YouTube Shorts, Instagram Reels, TikTok, and Facebook Reels.

The system must:
- Discover trending topics automatically
- Generate engaging scripts via LLM
- Produce voiceovers, visuals, and assembled videos
- Track analytics and performance
- Learn from what performs well (feedback loop)
- Scale to thousands of videos per day eventually

This is a software platform, not a script. Every component must be modular and replaceable without rewriting other parts.

---

## Core Principles (Never Violate These)

**Modularity first.** Every AI provider (LLM, TTS, image gen) sits behind an abstract base class. Swapping providers = writing a new class, nothing else.

**Open-source first.** Prefer Ollama, local models, and free APIs before paid ones. Paid APIs are optional plugins configured via `.env`.

**Local-first.** The entire system runs on local hardware. Cloud deployment is a future concern.

**Queue-driven.** No synchronous generation chains in API routes. Heavy work always goes through Celery tasks.

**Provider pattern everywhere.** Each service layer follows: `base.py` (abstract) → `provider_impl.py` (concrete) → selected via config/factory function.

---

## Target Content Niches

Currently seeded and supported: `science`, `history`, `programming`, `ai`, `trivia`

Priority niches for Phase 1: **science** and **history**.

---

## Hardware Context

The production machine is:
- GPU: NVIDIA GeForce RTX 3050 Laptop (4 GB VRAM)
- RAM: 15.3 GB
- CPU: AMD Ryzen 7 5800H (8 cores / 16 threads)

**Implications for all future work:**
- No Stable Diffusion in Phase 1 — 4 GB VRAM is unreliable for SD. Image generation uses Pillow slides.
- LLM: `qwen2.5:7b` via Ollama. It partially offloads to CPU with 4 GB VRAM. Works fine, just ~60-90s per script. `qwen2.5:3b` is available as a faster fallback.
- If adding image generation later, use SD 1.5 with `enable_model_cpu_offload()` and `enable_attention_slicing()` — not SDXL.
- Do not suggest or add models that require more than 4 GB VRAM without first making them optional via `.env`.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI (async) |
| Task Queue | Celery + Redis |
| Database | PostgreSQL via async SQLAlchemy 2.0 |
| Migrations | Alembic |
| LLM | Provider-agnostic via `services/llm/` — Groq (default), OpenAI, Anthropic, Gemini, Ollama |
| TTS | Edge TTS (Microsoft neural voices, free) |
| Image generation | Pillow gradient slides (Phase 1) / Pexels API (optional) |
| Video assembly | FFmpeg with Ken Burns effect |
| Queue monitoring | Flower |
| Containerisation | Docker + Docker Compose |

---

## Repository Layout

```
ai-content-factory/
├── CLAUDE.md                        ← this file
├── docker-compose.yml               ← services: api, worker, beat, flower, db, redis, ollama
├── Makefile                         ← all dev commands
├── .env.example                     ← copy to .env and fill in
├── .env                             ← gitignored, contains secrets
├── storage/
│   ├── audio/                       ← generated .mp3 files
│   ├── images/                      ← generated scene .png files
│   ├── videos/                      ← rendered .mp4 files
│   └── thumbnails/                  ← .jpg thumbnails
└── backend/
    ├── Dockerfile
    ├── requirements.txt
    ├── alembic.ini
    ├── alembic/
    │   ├── env.py                   ← async Alembic setup
    │   └── versions/
    │       └── 001_initial_schema.py ← full initial migration
    └── app/
        ├── main.py                  ← FastAPI app, CORS, router mount
        ├── core/
        │   ├── config.py            ← pydantic-settings Settings class
        │   ├── database.py          ← async engine, session, Base
        │   ├── celery_app.py        ← Celery config, beat schedule, task routing
        │   └── storage.py           ← path helpers for audio/image/video/thumbnail
        ├── models/                  ← SQLAlchemy ORM models
        │   ├── trend.py
        │   ├── topic.py
        │   ├── script.py
        │   └── video.py             ← also contains PublishingRecord, Analytics
        ├── schemas/                 ← Pydantic v2 request/response schemas
        │   ├── common.py
        │   ├── trend.py
        │   ├── topic.py
        │   ├── script.py
        │   └── video.py
        ├── services/
        │   ├── trend_discovery/
        │   │   ├── base.py          ← BaseTrendDiscoverer, DiscoveredTrend dataclass
        │   │   ├── reddit_discoverer.py
        │   │   ├── rss_discoverer.py
        │   │   └── orchestrator.py  ← runs all discoverers, deduplicates, saves to DB
        │   ├── llm/                 ← provider-agnostic LLM abstraction layer
        │   │   ├── base.py          ← BaseLLMClient.complete(system, user, ...) -> str
        │   │   ├── groq_client.py   ← Groq SDK (llama-3.3-70b, mixtral, gemma, …)
        │   │   ├── openai_client.py ← OpenAI SDK (gpt-4o, …)
        │   │   ├── anthropic_client.py ← Anthropic SDK (claude-opus-4-8, …)
        │   │   ├── gemini_client.py ← Google GenerativeAI SDK
        │   │   ├── ollama_client.py ← httpx → local Ollama REST API
        │   │   └── factory.py       ← get_llm_client(settings), get_quality_client(settings)
        │   ├── script_generation/
        │   │   ├── base.py          ← BaseScriptGenerator, GeneratedScript dataclass
        │   │   ├── prompts.py       ← system/user prompts, niche style guides, quality prompt
        │   │   ├── llm_generator.py ← LLMScriptGenerator(BaseLLMClient) — active implementation
        │   │   ├── ollama_generator.py ← legacy; kept for reference, not used
        │   │   └── quality_scorer.py ← QualityScorer(BaseLLMClient); scores 0-10, threshold 5.5
        │   ├── voice_generation/
        │   │   ├── base.py          ← BaseVoiceGenerator, VoiceGenerationResult dataclass
        │   │   └── edge_tts_generator.py
        │   ├── image_generation/
        │   │   ├── base.py          ← BaseImageGenerator, ImageGenerationResult dataclass
        │   │   ├── ffmpeg_slide_generator.py ← Pillow gradient slides, niche color palettes
        │   │   └── pexels_generator.py ← Pexels API with ffmpeg_slide fallback; get_image_generator() factory
        │   └── video_assembly/
        │       ├── base.py          ← BaseVideoAssembler, VideoAssemblyResult dataclass
        │       └── ffmpeg_assembler.py ← Ken Burns zoom/pan, concat, audio mux
        ├── tasks/
        │   ├── trend_tasks.py       ← discover_trends (queue: default, beat: hourly)
        │   ├── generation_tasks.py  ← generate_script (queue: generation)
        │   └── video_tasks.py       ← render_video (queue: video, time_limit: 900s)
        ├── api/
        │   └── v1/
        │       ├── router.py        ← mounts all routers under /api/v1
        │       ├── trends.py        ← GET /trends, POST /trends/discover
        │       ├── topics.py        ← CRUD + POST /{id}/generate-script
        │       ├── scripts.py       ← GET/approve + POST /{id}/render
        │       └── videos.py        ← GET + /download + /thumbnail
        └── scripts/
            ├── seed.py              ← seeds 16 starter topics (science + history)
            ├── generate_video.py    ← end-to-end CLI runner outside Celery
            └── run_discovery.py     ← manual trend discovery CLI
```

---

## Database Schema

All tables are in `backend/alembic/versions/001_initial_schema.py`. The ORM models are in `backend/app/models/`.

### trends
Discovered trending items from external sources.
- `id`, `source` (reddit/rss/google), `keyword`, `niche`, `score` (0.0-1.0), `raw_data` (JSONB), `url`, `discovered_at`

### topics
Curated content topics, either manually entered or derived from trends.
- `id`, `title`, `niche`, `description`, `status`, `priority` (1-10), `trend_id` (FK nullable), `created_at`, `updated_at`
- Status machine: `pending → selected → generating → done / rejected`

### scripts
LLM-generated scripts linked to a topic.
- `id`, `topic_id` (FK), `hook`, `main_content`, `cta`, `scenes` (JSONB array), `title`, `description`, `hashtags` (JSONB), `quality_score` (0-10), `quality_feedback` (JSONB), `model_used`, `voice_style`, `estimated_duration_seconds`, `version`, `status`, `created_at`
- Status machine: `draft → approved / rejected`
- Auto-approved if quality score ≥ 5.5

### videos
Rendered video files linked to a script.
- `id`, `topic_id` (FK), `script_id` (FK), `status`, `audio_path`, `image_paths` (JSONB), `video_path`, `thumbnail_path`, `render_time_seconds`, `duration_seconds`, `file_size_mb`, `error_message`, `render_metadata` (JSONB), `created_at`, `updated_at`
- Status machine: `queued → generating_audio → generating_images → assembling → rendered / failed`

### publishing_records
One record per platform a video is published to.
- `id`, `video_id` (FK), `platform` (youtube/instagram/tiktok), `platform_video_id`, `status`, `url`, `error_message`, `published_at`, `created_at`

### analytics
Performance metrics collected after publishing.
- `id`, `publishing_record_id` (FK), `views`, `likes`, `comments`, `shares`, `watch_time_avg_seconds`, `retention_rate`, `recorded_at`

---

## Content Pipeline Flow

```
Topic created (manually or from trend)
    ↓
POST /topics/{id}/generate-script
    → Celery task: generate_script
    → LLMScriptGenerator(get_llm_client(settings)).generate(topic, niche)
    → QualityScorer(get_quality_client(settings)).score(script)  [auto-approve if score ≥ 5.5]
    → Script saved to DB
    ↓
POST /scripts/{id}/approve  [if manual review needed]
    ↓
POST /scripts/{id}/render
    → Celery task: render_video
    → EdgeTTSGenerator.generate(full_text, audio_path)
    → ImageGenerator.generate(scene_prompt, image_path) × N scenes
    → FFmpegAssembler.assemble(audio, images, output)
    → Video saved to DB with status=rendered
    ↓
[Phase 3] POST /videos/{id}/publish
    → PublisherInterface.publish(video, platform)
```

---

## Celery Queue Configuration

Three queues — always preserve this routing:

| Queue | Purpose | Tasks |
|---|---|---|
| `default` | Fast/lightweight | Trend discovery |
| `generation` | LLM inference | Script generation |
| `video` | Long-running FFmpeg | Video rendering |

Beat schedule: `discover_trends` runs hourly at `:00`.

Worker startup command (in docker-compose):
```
celery -A app.core.celery_app worker --loglevel=info --concurrency=2 -Q default,generation,video
```

---

## Key Conventions

**Never break these patterns when adding features:**

1. **New AI provider** → create `backend/app/services/<layer>/new_provider.py` implementing the `Base*` class. Update the factory function or add a config key. Do not edit existing providers.

2. **New API route** → add a new file in `backend/app/api/v1/`, register it in `router.py`. Never add business logic to route handlers — call a service or dispatch a Celery task.

3. **New Celery task** → add to the appropriate task file, register the queue in `celery_app.py` task_routes. Use `bind=True` and `max_retries`.

4. **New database table** → add an ORM model in `backend/app/models/`, import it in `models/__init__.py`, write a new Alembic migration in `alembic/versions/`. Never use `Base.metadata.create_all()`.

5. **Config values** → always go in `backend/app/core/config.py` as a `Settings` field with a sane default. Access via `from app.core.config import settings`.

6. **File paths** → always use `app.core.storage` helpers (`audio_path()`, `image_path()`, etc.). Never hardcode paths.

7. **Async vs sync** → FastAPI routes and service methods are async. Celery tasks are sync wrappers that call `asyncio.run()` around async logic using `AsyncSessionLocal`.

---

## Environment Variables

All config lives in `.env` (gitignored). See `.env.example` for the full list. Key variables:

```
DATABASE_URL          postgresql+asyncpg://content_factory:content_factory@db:5432/content_factory
REDIS_URL             redis://redis:6379/0

# LLM (pick one provider setup)
LLM_PROVIDER          auto            # auto | groq | openai | anthropic | gemini | ollama
LLM_MODEL             llama-3.3-70b-versatile   # model name for your provider
LLM_QUALITY_MODEL     llama-3.1-8b-instant      # lighter model for quality scoring (optional)
GROQ_API_KEY          gsk_...         # for Groq
OPENAI_API_KEY        sk-...          # for OpenAI
ANTHROPIC_API_KEY     sk-ant-...      # for Anthropic
GEMINI_API_KEY        AIza...         # for Gemini

# Ollama (local fallback — used when LLM_MODEL contains ":")
OLLAMA_BASE_URL       http://ollama:11434
OLLAMA_MODEL          qwen2.5:7b

IMAGE_PROVIDER        ffmpeg_slides   # or: pexels
PEXELS_API_KEY        (optional)
VOICE_DEFAULT         en-US-GuyNeural
REDDIT_CLIENT_ID      (optional)
REDDIT_CLIENT_SECRET  (optional)
STORAGE_BASE_PATH     ./storage
DEFAULT_VIDEO_WIDTH   1080
DEFAULT_VIDEO_HEIGHT  1920
```

---

## How to Run Locally

```bash
# Start all services
docker compose up -d

# Run migrations (first time only)
docker compose exec api alembic upgrade head

# Pull the LLM into Ollama
docker compose exec ollama ollama pull qwen2.5:7b

# Seed 16 starter topics (science + history)
docker compose exec api python -m app.scripts.seed

# Generate your first video end-to-end
docker compose exec api python -m app.scripts.generate_video --topic-id 1

# Monitor Celery tasks
open http://localhost:5555  # Flower dashboard

# API docs
open http://localhost:8000/docs
```

## Makefile Commands

```
make up                  Start all Docker services
make down                Stop all services
make migrate             Run Alembic migrations
make seed                Seed starter topics
make pull-model          Pull qwen2.5:7b into Ollama
make pull-model-small    Pull qwen2.5:3b (faster, lower quality)
make generate TOPIC_ID=1 End-to-end video from a topic
make discover-trends     Run trend discovery manually
make queue-status        Show active Celery tasks
make logs                Tail api + worker logs
make test                Run pytest
```

---

## What Has Been Built (Phase 1 — Complete)

- [x] Full Docker Compose setup (api, worker, beat, flower, db, redis, ollama)
- [x] PostgreSQL schema with Alembic migration (001_initial_schema)
- [x] All ORM models (Trend, Topic, Script, Video, PublishingRecord, Analytics)
- [x] Pydantic v2 schemas for all models
- [x] Trend discovery: RSS (BBC, ScienceDaily, NYT, HN, Dev.to) + Reddit (optional, needs API keys)
- [x] Script generation: provider-agnostic `LLMScriptGenerator` via `services/llm/` layer; supports Groq, OpenAI, Anthropic, Gemini, Ollama; JSON-mode output, niche-specific style guides, scene breakdown
- [x] Quality scoring: `QualityScorer(BaseLLMClient)` — provider-agnostic; scores hook strength, clarity, virality, retention potential; auto-approve threshold 5.5/10
- [x] Voice generation: Edge TTS (Microsoft neural) — 6 voices (male/female US, GB, AU)
- [x] Image generation: Pillow gradient slides with niche color palettes (zero dependencies); Pexels API as optional upgrade
- [x] Video assembly: FFmpeg with Ken Burns zoom/pan effects, 1080×1920, audio mux, thumbnail extraction
- [x] Celery tasks for all three heavy stages (trend discovery, script generation, video rendering)
- [x] FastAPI REST API: `/api/v1/trends`, `/api/v1/topics`, `/api/v1/scripts`, `/api/v1/videos`
- [x] CLI scripts: `seed.py`, `generate_video.py` (end-to-end runner), `run_discovery.py`
- [x] 16 seeded topics across science and history niches

---

## What Needs to Be Built Next

### Phase 2 — Dashboard + Analytics (Next Priority)

Build a Next.js frontend dashboard. The backend API is already complete; this is purely a frontend task plus one new backend endpoint for aggregated analytics.

**Dashboard pages needed:**

1. **Queue Monitor** (`/`) — live view of Celery task states (pending/active/completed/failed). Poll `GET /api/v1/videos?status=queued` and `GET /api/v1/videos?status=rendering`. Show counts and a live feed.

2. **Topics** (`/topics`) — list all topics with status badges and priority. Allow creating new topics, changing priority, triggering script generation.

3. **Scripts** (`/scripts`) — list scripts with quality scores. Allow reviewing, approving, rejecting. Show hook/content/cta in a card. Trigger render from here.

4. **Videos** (`/videos`) — grid of rendered videos with thumbnails, duration, file size. Click to play in-browser. Download button. Link to approve for publishing.

5. **Trends** (`/trends`) — table of discovered trends with source/niche/score. Button to create a topic from a trend.

6. **Analytics** (`/analytics`) — charts of views/likes/retention over time per niche. Phase 3 will populate this; build the UI shell now.

**Frontend tech:** Next.js 14+ with App Router, Tailwind CSS, shadcn/ui components, TanStack Query for data fetching. Place in `frontend/` at the project root.

**New backend work for Phase 2:**
- Add `GET /api/v1/analytics/summary` endpoint — aggregated stats grouped by niche and time period
- Add `GET /api/v1/queue/status` endpoint — wraps Celery inspect to return active/scheduled task counts
- Add WebSocket or SSE endpoint for live task updates (optional enhancement)

### Phase 3 — Publishing Layer

Build provider-based publishing. Add to `backend/app/services/publishing/`.

```
base.py              ← BasePublisher.publish(video: Video, metadata: dict) -> PublishingResult
youtube_publisher.py ← YouTube Data API v3
tiktok_publisher.py
instagram_publisher.py
```

Add a new Celery task `publish_video` in `tasks/publishing_tasks.py`. Add `POST /api/v1/videos/{id}/publish` route accepting `platform` in the body.

YouTube is the highest priority — implement it first. Use `google-api-python-client` with OAuth2. Store tokens in the database (add a `platform_credentials` table).

### Phase 4 — Feedback Loop Engine

Build a service that reads analytics data and adjusts future generation.

```
backend/app/services/feedback/
    analyzer.py      ← queries analytics, ranks topics/hooks/voices by performance
    scorer.py        ← adjusts topic priority based on niche performance
    report.py        ← generates weekly performance summary
```

New Celery beat schedule: run feedback analysis weekly. Output should update `Topic.priority` and write a report to a new `performance_reports` table.

Key metrics to track: which niches perform best, which hooks get highest retention, which voice performs best per niche, optimal video length by niche.

---

## Known Limitations and TODOs

- **No auth** — the API has no authentication. Phase 2 should add JWT auth using `SECRET_KEY` from config. The `passlib` and `python-jose` dependencies are already in `requirements.txt`.
- **Reddit discoverer is optional** — it silently skips if `REDDIT_CLIENT_ID` is not set. This is intentional. RSS alone is sufficient.
- **Image quality** — Pillow slides are functional but plain. When upgrading, implement `StableDiffusionGenerator(BaseImageGenerator)` in `image_generation/`. Keep Pillow slides as the default until SD is explicitly enabled via `IMAGE_PROVIDER=stable_diffusion` in `.env`.
- **No tests yet** — `pytest` and `pytest-asyncio` are in requirements. Test files should go in `backend/tests/`. Priority: test the script generation prompt parsing and video assembly logic.
- **`updated_at` on topics** — SQLAlchemy's `onupdate=func.now()` does not fire on async updates via `setattr`. Either switch to a trigger in Alembic or manually set `updated_at` on each update.
- **Celery tasks use `asyncio.run()`** — this works but creates a new event loop per task. If concurrency issues arise, switch to using `asyncio.get_event_loop().run_until_complete()` or adopt `celery-pool-asyncio`.
