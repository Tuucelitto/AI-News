from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config import settings
from app.main import app
from app.models import ApiUsage, Article, Feed, SummaryStatus, utc_now
from app.services.queue import ModelSlot, QueueWorker
from app.services.rate_limiter import RateLimiter, next_quota_reset, quota_day
from tests.fakes import FakeClock, FakeSummarizer

LAST_FETCH = datetime(2026, 10, 30, 9, 0, tzinfo=UTC)


@pytest.fixture
def data(session: Session) -> None:
    feed = Feed(name="Example", url="https://example.com/rss", last_fetched_at=LAST_FETCH)
    session.add(feed)
    session.commit()
    statuses = [SummaryStatus.PENDING, SummaryStatus.PENDING, SummaryStatus.DONE]
    session.add_all(
        Article(
            feed_id=feed.id,
            guid=str(i),
            url=f"https://example.com/{i}",
            title="A",
            summary_status=s,
        )
        for i, s in enumerate(statuses)
    )
    session.add(ApiUsage(day=quota_day(utc_now()), model=settings.gemini_model, request_count=3))
    session.commit()


def test_status_without_scheduler(client: TestClient, data) -> None:
    body = client.get("/api/queue/status", headers={"X-Admin-Key": "test-admin-key"}).json()

    assert body["counts"] == {
        "new": 0,
        "pending": 2,
        "processing": 0,
        "done": 1,
        "skipped": 0,
        "failed": 0,
    }
    primary, fallback = body["models"]
    assert primary["model"] == settings.gemini_model
    assert primary["role"] == "primary"
    assert (primary["requests_today"], primary["daily_limit"]) == (3, settings.gemini_daily_limit)
    assert primary["paused_until"] is None
    assert fallback["model"] == settings.gemini_fallback_model
    assert fallback["requests_today"] == 0
    assert body["scheduler_running"] is False
    assert body["last_fetch_at"] == "2026-10-30T09:00:00Z"
    assert body["next_fetch_at"] is None


def test_status_with_running_scheduler(
    client: TestClient, data, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = utc_now()
    clock = FakeClock(now)
    paused_until = now + timedelta(minutes=2)
    worker = QueueWorker(
        ModelSlot(FakeSummarizer("flash", clock), RateLimiter("flash", 4, 18), paused_until),
        ModelSlot(FakeSummarizer("lite", clock), RateLimiter("lite", 12, 45)),
    )
    next_fetch = now + timedelta(minutes=30)
    scheduler = SimpleNamespace(
        running=True, get_job=lambda job_id: SimpleNamespace(next_run_time=next_fetch)
    )
    # monkeypatch removes the attribute again after the test.
    monkeypatch.setattr(
        app.state, "jobs", SimpleNamespace(scheduler=scheduler, worker=worker), raising=False
    )

    body = client.get("/api/queue/status", headers={"X-Admin-Key": "test-admin-key"}).json()

    primary, fallback = body["models"]
    assert datetime.fromisoformat(primary["paused_until"]) == paused_until
    assert fallback["paused_until"] is None
    assert datetime.fromisoformat(primary["quota_resets_at"]) == next_quota_reset(now)
    assert body["scheduler_running"] is True
    assert datetime.fromisoformat(body["next_fetch_at"]) == next_fetch


def test_queue_status_needs_the_admin_key(client: TestClient) -> None:
    assert client.get("/api/queue/status").status_code == 401
