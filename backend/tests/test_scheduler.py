import logging
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest
from sqlmodel import Session, select

from app.config import settings
from app.models import Article, Feed, SummaryStatus
from app.scheduler import (
    FETCH_JOB_ID,
    SUMMARY_JOB_ID,
    create_scheduler,
    fetch_job,
    start_background_jobs,
    summary_job,
)
from app.services.queue import ModelSlot, QueueWorker
from app.services.rate_limiter import RateLimiter
from tests.fakes import FakeClock, FakeSummarizer


def make_worker() -> QueueWorker:
    clock = FakeClock(datetime.now(UTC))
    slot = ModelSlot(FakeSummarizer("flash", clock), RateLimiter("flash", 600, 18))
    return QueueWorker(slot, clock=clock)


def broken_session_factory() -> Session:
    raise RuntimeError("database is down")


def test_fetch_job_fetches_and_extracts(session: Session) -> None:
    session.add(Feed(name="Example", url="https://news.example.com/rss"))
    session.commit()
    # Dated relative to now, so the entry is always within FETCH_MAX_AGE_HOURS.
    published = format_datetime(datetime.now(UTC) - timedelta(hours=1), usegmt=True)
    feed_xml = f"""<?xml version="1.0"?><rss version="2.0"><channel><title>T</title>
        <item><title>Fresh story</title><link>https://news.example.com/fresh</link>
        <guid>fresh</guid><pubDate>{published}</pubDate><description>Short teaser.</description>
        </item></channel></rss>"""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/rss":
            return httpx.Response(200, text=feed_xml)
        return httpx.Response(404)  # article page: falls back to the RSS teaser

    fetch_job(
        session_factory=lambda: session,
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(handler)),
    )

    article = session.exec(select(Article)).one()
    assert article.title == "Fresh story"
    assert article.summary_status == SummaryStatus.SKIPPED  # extraction ran; teaser is short


def test_fetch_job_logs_errors_instead_of_raising(caplog: pytest.LogCaptureFixture) -> None:
    fetch_job(session_factory=broken_session_factory)

    assert "Fetch job failed" in caplog.text


def test_summary_job_processes_one_batch(
    session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    feed = Feed(name="Example", url="https://news.example.com/rss")
    session.add(feed)
    session.commit()
    session.add_all(
        Article(
            feed_id=feed.id,
            guid=str(i),
            url=f"https://news.example.com/{i}",
            title=f"Article {i}",
            content="Some text.",
            summary_status=SummaryStatus.PENDING,
        )
        for i in range(2)
    )
    session.commit()
    caplog.set_level(logging.INFO)

    summary_job(make_worker(), session_factory=lambda: session)

    statuses = session.exec(select(Article.summary_status)).all()
    assert statuses == [SummaryStatus.DONE, SummaryStatus.DONE]
    assert "flash: summarized (done=2" in caplog.text


def test_summary_job_logs_errors_instead_of_raising(caplog: pytest.LogCaptureFixture) -> None:
    summary_job(make_worker(), session_factory=broken_session_factory)

    assert "Summary job failed" in caplog.text


def test_scheduler_has_both_jobs_with_configured_intervals() -> None:
    scheduler = create_scheduler(make_worker())

    jobs = {job.id: job for job in scheduler.get_jobs()}
    assert jobs[FETCH_JOB_ID].trigger.interval == timedelta(minutes=settings.fetch_interval_minutes)
    assert jobs[SUMMARY_JOB_ID].trigger.interval == timedelta(
        seconds=settings.summary_interval_seconds
    )
    assert not scheduler.running  # created, not started: no real jobs run in tests


def test_without_worker_only_fetching_is_scheduled() -> None:
    scheduler = create_scheduler(worker=None)

    assert [job.id for job in scheduler.get_jobs()] == [FETCH_JOB_ID]


def test_scheduler_is_not_started_when_disabled() -> None:
    assert settings.scheduler_enabled is False  # set in conftest.py
    assert start_background_jobs() is None
