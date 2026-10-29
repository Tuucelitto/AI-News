"""Fetch all active feeds once and store new articles in the database.

Usage (from backend/):
    uv run python -m scripts.fetch_now
"""

import logging

from sqlmodel import Session, func, select

from app.db import engine, init_db
from app.models import Article
from app.seed import seed_feeds
from app.services.fetcher import create_http_client, fetch_all_feeds


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    init_db()

    with Session(engine) as session, create_http_client() as client:
        seed_feeds(session)
        results = fetch_all_feeds(client, session)
        total = session.exec(select(func.count()).select_from(Article)).one()

    width = max(len(result.feed_name) for result in results)
    for result in results:
        if result.error:
            status = f"error: {result.error}"
        elif result.not_modified:
            status = "not modified"
        else:
            status = f"{result.new_articles} new"
        print(f"{result.feed_name.ljust(width)}  {status}")

    print(f"\n{sum(r.new_articles for r in results)} new articles, {total} in database")


if __name__ == "__main__":
    main()
