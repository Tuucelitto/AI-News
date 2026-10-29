# AI News

Collects AI news from RSS feeds, extracts full article text, summarizes long articles in Turkish with the
Gemini API (free tier, Flash model) through a rate-limited queue, and serves them through a Vue web app.

The full architecture and step-by-step roadmap live in `docs/PLAN.md`. Read it before starting a step,
and tick the step's checkbox there when it is done.

## Stack

- **Backend (`backend/`):** Python, FastAPI, SQLModel, SQLite, feedparser, trafilatura, google-genai, APScheduler, pytest.
- **Frontend (`frontend/`):** Vue 3 (Composition API, `<script setup>`), Vite, TypeScript, Pinia, Vue Router, Tailwind CSS.

## Commands

Python dependencies are managed with **uv** (`pyproject.toml` + `uv.lock`). Use `uv add` / `uv add --dev`, never `pip install`.

```bash
# backend (run inside backend/)
uv sync                       # install dependencies into .venv
uv run fastapi dev            # dev server with reload, http://localhost:8000/docs
uv run pytest                 # tests
uv run ruff check . && uv run ruff format .
uv run python -m scripts.check_sources   # check every feed in sources.yaml
uv run python -m scripts.fetch_now       # fetch all feeds once into the database

# frontend
# (added in step 9a)
```

## Architecture rules

- **Layering:** `api/` → `services/` → `models`. Route handlers contain no business logic; `scheduler.py` only calls service functions.
- **Gemini is only called from the summary queue worker** (`services/queue.py` → `services/summarizer.py`).
  Never call it from a request handler or in a loop. Every call must go through `rate_limiter.py`.
- **The queue is the database:** `Article.summary_status` (`new/pending/processing/done/skipped/failed`) plus
  `next_attempt_at` and `summary_attempts`. Do not introduce Redis/Celery or in-memory queues.
- **No hard-coded limits or model names.** RPM, daily limit, thresholds and `GEMINI_MODEL` come from settings (`config.py` / `.env`).
- **Single scheduler instance:** run uvicorn with one worker; the scheduler is started in the FastAPI `lifespan` and guarded by `SCHEDULER_ENABLED`.
- Background jobs are synchronous and run in threads; each job opens its own DB session. SQLite runs in WAL mode.
- API responses use dedicated read schemas; never expose `Article.content` (full extracted text) to the client.
- The UI shows summaries and links to the original source, never the full scraped text.

## Conventions

- Code, identifiers, comments, commit messages and README: **English**.
- Generated summaries (`title_tr`, `summary_tr`, `key_points`) are Turkish.
- Python: type hints everywhere, Ruff for lint/format, `datetime` values in UTC.
- Frontend: typed API client in `src/api/`, shared types in `src/types/`, one Pinia store per domain.

## Secrets

- Secrets (`GEMINI_API_KEY`, `ADMIN_API_KEY`) live only in `backend/.env`, which is git-ignored.
  Keep `backend/.env.example` updated with every new setting (empty values).

## Testing

- Tests must never hit the real Gemini API or real RSS feeds: use a fake summarizer client and files in `backend/tests/fixtures/`.
- Use an in-memory SQLite database per test.
- Prioritize tests for queue state transitions, backoff, rate limiting, deduplication and the long/short decision.
