"""Fetch all active feeds once, then extract the full text of new articles.

Usage (from backend/):
    uv run python -m scripts.fetch_now
"""

import logging

from sqlmodel import Session, func, select

from app.db import engine, init_db
from app.models import Article, SummaryStatus
from app.seed import seed_feeds
from app.services.extractor import process_new_articles
from app.services.fetcher import create_http_client, fetch_all_feeds


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # hide one log line per request
    init_db()

    with Session(engine) as session, create_http_client() as client:
        seed_feeds(session)
        results = fetch_all_feeds(client, session)

        width = max(len(result.feed_name) for result in results)
        for result in results:
            if result.error:
                status = f"error: {result.error}"
            elif result.not_modified:
                status = "not modified"
            else:
                status = f"{result.new_articles} new"
            print(f"{result.feed_name.ljust(width)}  {status}")
        print(f"\n{sum(r.new_articles for r in results)} new articles. Extracting text...")

        counts = process_new_articles(client, session, limit=500)
        total = session.exec(select(func.count()).select_from(Article)).one()

    print(
        f"{counts[SummaryStatus.PENDING]} queued for summary, "
        f"{counts[SummaryStatus.SKIPPED]} too short (skipped). {total} articles in database."
    )


if __name__ == "__main__":
    main()
