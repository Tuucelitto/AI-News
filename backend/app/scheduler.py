"""Background jobs: fetch feeds every hour and keep the summary queue moving.

Jobs run in BackgroundScheduler threads, so API requests are never blocked by them.
Run the app with a single worker process: each process would start its own scheduler
and every job would run twice.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC

from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import Session

from app.config import settings
from app.db import engine
from app.models import SummaryStatus, utc_now
from app.services.extractor import process_new_articles
from app.services.fetcher import create_http_client, fetch_all_feeds
from app.services.queue import Outcome, QueueWorker, create_worker

logger = logging.getLogger(__name__)

FETCH_JOB_ID = "fetch"
SUMMARY_JOB_ID = "summary"

SessionFactory = Callable[[], Session]


def _new_session() -> Session:
    # Every job run gets its own session: sessions must not be shared between threads.
    return Session(engine)


@dataclass
class BackgroundJobs:
    scheduler: BackgroundScheduler
    worker: QueueWorker | None  # None when summaries are disabled (no API key)


def fetch_job(
    session_factory: SessionFactory = _new_session,
    client_factory: Callable = create_http_client,
) -> None:
    """Fetch all feeds, then extract the text of the new articles."""
    try:
        with session_factory() as session, client_factory() as client:
            results = fetch_all_feeds(client, session)
            counts = process_new_articles(client, session, limit=500)
    except Exception:  # a crashing job must not take the scheduler down
        logger.exception("Fetch job failed")
        return

    failed = [result.feed_name for result in results if result.error]
    logger.info(
        "Fetched %d new articles (failed feeds: %s); %d queued for summary, %d skipped",
        sum(result.new_articles for result in results),
        ", ".join(failed) or "none",
        counts[SummaryStatus.PENDING],
        counts[SummaryStatus.SKIPPED],
    )


def summary_job(worker: QueueWorker, session_factory: SessionFactory = _new_session) -> None:
    """Send at most one batch to Gemini. Cheap when there is nothing to do or we must wait."""
    try:
        with session_factory() as session:
            result = worker.run_once(session)
    except Exception:
        logger.exception("Summary job failed")
        return

    if result.outcome in (Outcome.SUMMARIZED, Outcome.REQUEST_FAILED):
        logger.info(
            "%s: %s (done=%d, retrying=%d, failed=%d)",
            result.model,
            result.outcome.value,
            result.done,
            result.retrying,
            result.failed,
        )


def create_scheduler(worker: QueueWorker | None) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(
        timezone=UTC,
        # max_instances: never run a job twice in parallel (a Gemini call can take minutes).
        # coalesce: runs missed meanwhile are merged into one instead of piling up.
        job_defaults={"max_instances": 1, "coalesce": True},
    )
    scheduler.add_job(
        fetch_job,
        "interval",
        minutes=settings.fetch_interval_minutes,
        id=FETCH_JOB_ID,
        next_run_time=utc_now(),  # also fetch right after startup
    )
    if worker is not None:
        scheduler.add_job(
            summary_job,
            "interval",
            seconds=settings.summary_interval_seconds,
            args=[worker],
            id=SUMMARY_JOB_ID,
        )
    return scheduler


def start_background_jobs() -> BackgroundJobs | None:
    if not settings.scheduler_enabled:
        logger.info("Scheduler disabled (SCHEDULER_ENABLED=false)")
        return None

    try:
        worker = create_worker()
    except ValueError as exc:  # e.g. missing API key: keep fetching, skip summaries
        logger.warning("Summaries disabled: %s", exc)
        worker = None

    scheduler = create_scheduler(worker)
    scheduler.start()
    logger.info("Scheduler started with jobs: %s", [job.id for job in scheduler.get_jobs()])
    return BackgroundJobs(scheduler, worker)


def stop_background_jobs(jobs: BackgroundJobs | None) -> None:
    if jobs is not None:
        # Do not wait for a running Gemini call; articles it leaves in "processing"
        # are reset on the next startup.
        jobs.scheduler.shutdown(wait=False)
