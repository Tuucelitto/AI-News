"""Run the summary queue for a limited number of Gemini requests and show progress.

Summaries ARE saved to the database. Each request summarizes up to SUMMARY_BATCH_SIZE articles.

Usage (from backend/):
    uv run python -m scripts.run_queue                    # at most 2 requests
    uv run python -m scripts.run_queue --max-requests 5
"""

import argparse
import logging
import time

from sqlmodel import Session, func, select

from app.db import engine, init_db
from app.models import Article, utc_now
from app.services.queue import Outcome, create_worker, reset_stuck_articles

MAX_WAIT_SECONDS = 120  # stop instead of waiting longer than this


def print_status(session: Session, worker) -> None:
    counts = session.exec(
        select(Article.summary_status, func.count()).group_by(Article.summary_status)
    ).all()
    print("\nArticles:", ", ".join(f"{status.value}={count}" for status, count in counts))
    now = utc_now()
    for slot in filter(None, (worker.primary, worker.fallback)):
        limiter = slot.limiter
        used = limiter.requests_today(session, now)
        print(f"Quota {limiter.model}: {used}/{limiter.daily_limit} today")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--max-requests", type=int, default=2)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    init_db()
    worker = create_worker()
    requests = 0

    with Session(engine) as session:
        if reset := reset_stuck_articles(session):
            print(f"Reset {reset} articles stuck in processing.")

        while requests < args.max_requests:
            result = worker.run_once(session)

            if result.outcome == Outcome.IDLE:
                print("Queue is empty.")
                break
            if result.outcome == Outcome.WAITING:
                wait = (result.next_run_at - utc_now()).total_seconds()
                if wait > MAX_WAIT_SECONDS:
                    print(f"Next request possible at {result.next_run_at:%Y-%m-%d %H:%M} UTC.")
                    break
                print(f"Waiting {wait:.0f}s for the rate limit...")
                time.sleep(max(wait, 0) + 0.1)
                continue

            requests += 1
            line = (
                f"[{requests}] {result.model}: {result.outcome.value} "
                f"(done={result.done}, retrying={result.retrying}, failed={result.failed})"
            )
            print(line + (f" - {result.error}" if result.error else ""))

        print_status(session, worker)


if __name__ == "__main__":
    main()
