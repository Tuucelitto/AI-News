from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlmodel import Session, select

from app.models import Article, Feed, SummaryStatus
from app.services.queue import ModelSlot, Outcome, QueueWorker, RunResult, reset_stuck_articles
from app.services.rate_limiter import RateLimiter
from app.services.summarizer import PermanentSummaryError, TransientSummaryError
from tests.fakes import FakeClock, FakeSummarizer, Slow

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=2)  # past every pause and backoff used below
QUOTA_RESET = datetime(2026, 10, 31, 7, 0, tzinfo=UTC)


def make_worker(
    primary_results: Sequence[Any] = (),
    fallback_results: Sequence[Any] | None = None,
    daily_limit: int = 18,
) -> QueueWorker:
    clock = FakeClock(NOW)

    def slot(model: str, results: Sequence[Any]) -> ModelSlot:
        # High RPM so that tests are not slowed down by per-minute spacing.
        return ModelSlot(
            FakeSummarizer(model, clock, results), RateLimiter(model, 600, daily_limit)
        )

    fallback = slot("lite", fallback_results) if fallback_results is not None else None
    return QueueWorker(
        slot("flash", primary_results), fallback, batch_size=5, max_attempts=3, clock=clock
    )


def run(worker: QueueWorker, session: Session, at: datetime) -> RunResult:
    worker.clock.now = at
    return worker.run_once(session)


def add_pending(session: Session, count: int) -> list[Article]:
    """Pending articles; a higher index means a newer article."""
    feed = Feed(name="Example", url="https://example.com/rss")
    session.add(feed)
    session.commit()
    articles = [
        Article(
            feed_id=feed.id,
            guid=str(i),
            url=f"https://example.com/{i}",
            title=f"Article {i}",
            content="Some text.",
            summary_status=SummaryStatus.PENDING,
            published_at=NOW - timedelta(hours=count - i),
        )
        for i in range(count)
    ]
    session.add_all(articles)
    session.commit()
    return articles


def batches(worker: QueueWorker, slot: str = "primary") -> list[list[int]]:
    return getattr(worker, slot).summarizer.batches


def test_successful_batch_is_saved(session: Session) -> None:
    articles = add_pending(session, 3)
    worker = make_worker()

    result = run(worker, session, NOW)

    assert (result.outcome, result.model, result.done) == (Outcome.SUMMARIZED, "flash", 3)
    for article in articles:
        assert article.summary_status == SummaryStatus.DONE
        assert article.title_tr == f"Başlık {article.id}"
        assert article.key_points == ["Nokta"]
        assert article.model_used == "flash"
        assert article.summarized_at == NOW
        assert article.content is None  # the publisher's full text is not kept
    assert worker.primary.limiter.requests_today(session, NOW) == 1


def test_newest_articles_go_first_in_batches(session: Session) -> None:
    articles = add_pending(session, 7)
    worker = make_worker()

    run(worker, session, NOW)

    newest_five = [a.id for a in reversed(articles[2:])]
    assert batches(worker) == [newest_five]
    assert articles[0].summary_status == SummaryStatus.PENDING


def test_empty_queue_is_idle(session: Session) -> None:
    assert run(make_worker(), session, NOW).outcome == Outcome.IDLE


def test_articles_are_not_claimed_before_their_retry_time(session: Session) -> None:
    (article,) = add_pending(session, 1)
    article.summary_attempts = 1
    article.next_attempt_at = NOW + timedelta(minutes=5)
    session.commit()

    assert run(make_worker(), session, NOW).outcome == Outcome.IDLE


def test_article_missing_from_response_is_retried_alone_with_backoff(session: Session) -> None:
    a, b = add_pending(session, 2)
    worker = make_worker(primary_results=[[b.id]])

    result = run(worker, session, NOW)

    assert (result.done, result.retrying) == (1, 1)
    assert a.summary_status == SummaryStatus.PENDING
    assert a.summary_attempts == 1
    assert a.next_attempt_at == NOW + timedelta(minutes=5)

    run(worker, session, LATER)

    assert batches(worker)[-1] == [a.id]
    assert a.summary_status == SummaryStatus.DONE


def test_article_fails_after_max_attempts(session: Session) -> None:
    (article,) = add_pending(session, 1)
    worker = make_worker(primary_results=[[], [], []])

    for hours in range(3):
        worker.primary.limiter.last_request_at = None
        run(worker, session, NOW + timedelta(hours=hours * 3))

    assert article.summary_status == SummaryStatus.FAILED
    assert article.summary_attempts == 3
    assert article.summary_error == "Missing from model response"
    assert article.content is None


def test_transient_error_pauses_model_without_counting_attempts(session: Session) -> None:
    articles = add_pending(session, 2)
    worker = make_worker(primary_results=[TransientSummaryError("504 DEADLINE_EXCEEDED")])

    result = run(worker, session, NOW)

    assert result.outcome == Outcome.REQUEST_FAILED
    for article in articles:
        assert article.summary_status == SummaryStatus.PENDING
        assert article.summary_attempts == 0
        assert article.content == "Some text."  # needed for the next attempt
    assert worker.primary.paused_until == NOW + timedelta(minutes=1)
    # The failed request still counts against the daily quota.
    assert worker.primary.limiter.requests_today(session, NOW) == 1

    waiting = run(worker, session, NOW + timedelta(seconds=30))
    assert (waiting.outcome, waiting.next_run_at) == (Outcome.WAITING, NOW + timedelta(minutes=1))


def test_pause_grows_with_consecutive_failures(session: Session) -> None:
    add_pending(session, 1)
    error = TransientSummaryError("503")
    worker = make_worker(primary_results=[error, error, error])

    run(worker, session, NOW)
    run(worker, session, NOW + timedelta(minutes=1))
    run(worker, session, NOW + timedelta(minutes=3))

    assert worker.primary.paused_until == NOW + timedelta(minutes=3 + 4)


def test_server_suggested_retry_delay_is_used(session: Session) -> None:
    add_pending(session, 1)
    worker = make_worker(primary_results=[TransientSummaryError("429", retry_after=37)])

    run(worker, session, NOW)

    assert worker.primary.paused_until == NOW + timedelta(seconds=37)


def test_fallback_is_used_while_primary_is_paused(session: Session) -> None:
    articles = add_pending(session, 2)
    worker = make_worker(primary_results=[TransientSummaryError("504")], fallback_results=[])

    run(worker, session, NOW)
    result = run(worker, session, NOW + timedelta(seconds=5))

    assert (result.outcome, result.model) == (Outcome.SUMMARIZED, "lite")
    assert all(article.model_used == "lite" for article in articles)


def test_pause_starts_when_a_slow_request_fails(session: Session) -> None:
    """Regression: a 504 arrives after a 120 s timeout. The pause must count from then,
    otherwise it is already over and the failing model is tried again at once."""
    add_pending(session, 1)
    timeout = Slow(120, TransientSummaryError("504 DEADLINE_EXCEEDED"))
    worker = make_worker(primary_results=[timeout], fallback_results=[])

    run(worker, session, NOW)
    assert worker.primary.paused_until == NOW + timedelta(seconds=120 + 60)

    result = run(worker, session, NOW + timedelta(seconds=121))
    assert result.model == "lite"


def test_primary_is_used_again_after_its_pause(session: Session) -> None:
    add_pending(session, 1)
    worker = make_worker(primary_results=[TransientSummaryError("504")], fallback_results=[])
    run(worker, session, NOW)

    result = run(worker, session, NOW + timedelta(minutes=2))

    assert result.model == "flash"


def test_fallback_is_not_used_for_normal_per_minute_spacing(session: Session) -> None:
    add_pending(session, 10)
    worker = make_worker(fallback_results=[])
    worker.primary.limiter.min_interval = timedelta(seconds=15)

    run(worker, session, NOW)
    result = run(worker, session, NOW + timedelta(seconds=5))

    assert (result.outcome, result.next_run_at) == (Outcome.WAITING, NOW + timedelta(seconds=15))
    assert batches(worker, "fallback") == []


def test_daily_quota_switches_to_fallback(session: Session) -> None:
    add_pending(session, 10)
    exhausted = TransientSummaryError("429 per day", daily_quota_exhausted=True)
    worker = make_worker(primary_results=[exhausted], fallback_results=[])

    run(worker, session, NOW)
    result = run(worker, session, NOW + timedelta(seconds=5))

    assert worker.primary.limiter.requests_today(session, NOW) == 18
    assert result.model == "lite"


def test_without_fallback_waits_for_quota_reset(session: Session) -> None:
    add_pending(session, 10)
    worker = make_worker(daily_limit=1)

    run(worker, session, NOW)
    result = run(worker, session, NOW + timedelta(minutes=1))

    assert (result.outcome, result.next_run_at) == (Outcome.WAITING, QUOTA_RESET)


def test_permanent_error_in_batch_retries_each_article_alone(session: Session) -> None:
    culprit, innocent = add_pending(session, 2)  # innocent is newer, so it goes first
    blocked = PermanentSummaryError("Prompt blocked: SAFETY")
    worker = make_worker(primary_results=[blocked, "all", blocked])

    run(worker, session, NOW)
    # We cannot tell which article caused the block, so both get one attempt.
    assert culprit.summary_attempts == innocent.summary_attempts == 1
    assert culprit.summary_status == innocent.summary_status == SummaryStatus.PENDING

    run(worker, session, LATER)
    run(worker, session, LATER + timedelta(minutes=1))

    assert batches(worker) == [[innocent.id, culprit.id], [innocent.id], [culprit.id]]
    assert innocent.summary_status == SummaryStatus.DONE
    assert culprit.summary_status == SummaryStatus.FAILED  # blocked when sent alone
    assert culprit.summary_error == "Prompt blocked: SAFETY"


def test_unexpected_error_releases_articles(session: Session) -> None:
    (article,) = add_pending(session, 1)
    worker = make_worker(primary_results=[RuntimeError("bug")])

    with pytest.raises(RuntimeError):
        run(worker, session, NOW)

    assert article.summary_status == SummaryStatus.PENDING


def test_reset_stuck_articles(session: Session) -> None:
    articles = add_pending(session, 3)
    articles[0].summary_status = SummaryStatus.PROCESSING
    articles[1].summary_status = SummaryStatus.PROCESSING
    session.commit()

    assert reset_stuck_articles(session) == 2
    statuses = session.exec(select(Article.summary_status)).all()
    assert statuses == [SummaryStatus.PENDING] * 3
