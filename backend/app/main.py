import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from app.api import articles, feeds, health, queue
from app.config import settings
from app.db import engine, init_db
from app.scheduler import start_background_jobs, stop_background_jobs
from app.seed import seed_feeds
from app.services.queue import reset_stuck_articles


def configure_logging() -> None:
    # Python's default level is WARNING, which would hide our job progress messages.
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    # These log every HTTP request or every job run; too noisy at INFO.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.ERROR)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    init_db()
    with Session(engine) as session:
        seed_feeds(session)
        reset_stuck_articles(session)
    app.state.jobs = start_background_jobs()
    yield
    stop_background_jobs(app.state.jobs)


app = FastAPI(title="AI News API", lifespan=lifespan)

# Only needed when the frontend is served from another origin; in development Vite proxies /api.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-Admin-Key"],
)

for module in (health, articles, feeds, queue):
    app.include_router(module.router, prefix="/api")
