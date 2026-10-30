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
uv run alembic revision --autogenerate -m "..."   # after changing app/models.py (review the file!)
uv run alembic upgrade head   # also runs automatically on app startup (app.db.init_db)
uv run python -m scripts.check_sources   # check every feed in sources.yaml
uv run python -m scripts.fetch_now       # fetch all feeds once into the database
uv run python -m scripts.try_summary     # summarize one batch, print only (uses 1 Gemini request!)
uv run python -m scripts.run_queue       # summarize and SAVE, max 2 requests (--max-requests N)

# frontend (run inside frontend/; Node ^22.18, npm 11 — npm 10 crashes on install)
npm install
npm run dev                   # http://localhost:5173, proxies /api to 127.0.0.1:8000
npx vitest run                # unit tests (npm run test:unit starts watch mode)
npm run type-check && npm run lint && npm run build
npm run lint:check && npm run format:check   # what CI runs: check only, never --fix
```

## Architecture rules

- **Layering:** `api/` → `services/` → `models`. Route handlers contain no business logic; `scheduler.py` only calls service functions.
- **Gemini is only called from the summary queue worker** (`services/queue.py` → `services/summarizer.py`).
  Never call it from a request handler or in a loop. Every call must go through `rate_limiter.py`
  (only `scripts/try_summary.py` bypasses it, for manual prompt checks).
- Service errors (429/5xx/timeouts) pause the model and switch to `GEMINI_FALLBACK_MODEL`; they never count as
  article attempts. Time in `QueueWorker` comes from its injected `clock`, so tests can simulate slow requests.
- **The queue is the database:** `Article.summary_status` (`new/pending/processing/done/skipped/failed`) plus
  `next_attempt_at` and `summary_attempts`. Do not introduce Redis/Celery or in-memory queues.
- **No hard-coded limits or model names.** RPM, daily limit, thresholds and `GEMINI_MODEL` come from settings (`config.py` / `.env`).
- **Single scheduler instance:** run uvicorn with one worker; the scheduler is started in the FastAPI `lifespan` and guarded by `SCHEDULER_ENABLED`.
  Only ONE app process may run against the same database: a second one (e.g. a forgotten `fastapi dev` that hot-reloaded)
  starts a second scheduler and both work the same queue. Before starting the app for a manual test, check
  `lsof -nP -iTCP -sTCP:LISTEN | grep python`; use `SCHEDULER_ENABLED=false` for API-only runs.
- Background jobs are synchronous and run in threads; each job opens its own DB session. SQLite runs in WAL mode.
- API responses use dedicated read schemas; never expose `Article.content` (full extracted text) to the client.
- `Article.content` is temporary: it is deleted when an article is done, failed or skipped, so a summary request
  must never rely on it being there later. `resummarize` downloads the text again. SQLite runs with `secure_delete=ON`.
- The status dashboard is admin-only: `/api/queue/status` needs `AdminDep`, the route uses `meta.requiresAdmin`.
- Favorites live in `localStorage` (`stores/favorites.ts`): no accounts, nothing stored on the server.
- Every write endpoint (POST/PATCH/PUT/DELETE) must declare `dependencies=[AdminDep]`; `test_admin_api.py` fails otherwise.
- `sources.yaml` only seeds an empty database. After that, feeds are managed through the API.
- **Schema changes need an Alembic migration** (`backend/migrations/versions/`). Never delete the database to change
  the schema. `test_migrations.py` fails if models and migrations drift apart. Tests themselves use `create_tables()`.
- Search uses the `search_fold()` SQL function (`app/search.py`, registered per SQLite connection): I/İ/ı → i, accents
  dropped. Apply it to both the column and the query.
- The UI shows summaries and links to the original source, never the full scraped text.

## Conventions

- Code, identifiers, comments, commit messages and README: **English**.
- Generated summaries (`title_tr`, `summary_tr`, `key_points`) are Turkish.
- Python: type hints everywhere, Ruff for lint/format, `datetime` values in UTC.
- Frontend: typed API client in `src/api/client.ts` (components never call `fetch` directly), types mirroring
  `backend/app/schemas.py` in `src/types/api.ts` (update both together), one Pinia store per domain (setup syntax),
  lazy-loaded views. UI text is Turkish; code and API error messages are English.
- Styling: Tailwind; reuse the `card`, `btn`, `btn-primary`, `input-field` utilities from `src/assets/main.css` and give
  every color a `dark:` variant. Show API errors through `errorMessage()` (`src/utils/errors.ts`, Turkish text).
- Never use `window.confirm/alert/prompt` (they block the page and browser automation); use inline confirmation.

## Secrets

- Secrets (`GEMINI_API_KEY`, `ADMIN_API_KEY`) live only in `backend/.env`, which is git-ignored.
  Keep `backend/.env.example` updated with every new setting (empty values).

## Testing

- CI (`.github/workflows/ci.yml`) runs ruff check/format --check + pytest and npm lint:check, format:check,
  type-check, vitest, build on every push/PR. Keep it green; it needs no secrets.

- Tests must never hit the real Gemini API or real RSS feeds: use a fake summarizer client and files in `backend/tests/fixtures/`.
- Use an in-memory SQLite database per test.
- Prioritize tests for queue state transitions, backoff, rate limiting, deduplication and the long/short decision.
