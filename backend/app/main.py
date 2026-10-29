import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import Session

from app.api import articles, feeds, health, queue
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

for module in (health, articles, feeds, queue):
    app.include_router(module.router, prefix="/api")
