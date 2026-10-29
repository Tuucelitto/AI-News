from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import Session

from app.api import articles, feeds, health
from app.db import engine, init_db
from app.seed import seed_feeds


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    with Session(engine) as session:
        seed_feeds(session)
    yield


app = FastAPI(title="AI News API", lifespan=lifespan)

for module in (health, articles, feeds):
    app.include_router(module.router, prefix="/api")
