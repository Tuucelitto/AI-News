"""The summary queue: picks pending articles, sends them to Gemini in batches and
records the outcome. The queue itself is the `summary_status` column of Article.

Error policy:
- Service problems (429, 5xx, timeouts) are not the articles' fault: the articles go
  back to pending unchanged and the model is paused. While the main model is paused
  or out of daily quota, the fallback model is used.
- Article problems (missing from the response, permanent errors) count as an attempt.
  Articles that failed before are retried alone, so one bad article cannot keep
  blocking the others in its batch.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from sqlmodel import Session, col, or_, select, update

from app.config import settings
from app.models import Article, SummaryStatus, utc_now
from app.services.rate_limiter import RateLimiter
from app.services.summarizer import (
    ArticleInput,
    ArticleSummary,
    GeminiSummarizer,
    PermanentSummaryError,
    Summarizer,
    TransientSummaryError,
)

logger = logging.getLogger(__name__)

RETRY_BACKOFF_BASE = timedelta(minutes=5)  # per article: 5, 10, 20, 40 min
PAUSE_BASE = timedelta(minutes=1)  # per model after service errors: 1, 2, 4... min
MAX_PAUSE = timedelta(minutes=30)


class Outcome(StrEnum):
    SUMMARIZED = "summarized"  # a request was made and returned summaries
    REQUEST_FAILED = "request_failed"  # a request was made but failed
    WAITING = "waiting"  # rate limit or pause; try again at next_run_at
    IDLE = "idle"  # nothing to summarize


@dataclass
class RunResult:
    outcome: Outcome
    model: str | None = None
    done: int = 0
    retrying: int = 0
    failed: int = 0
    error: str | None = None
    next_run_at: datetime | None = None


@dataclass
class ModelSlot:
    """A model with its own rate limiter and pause state."""

    summarizer: Summarizer
    limiter: RateLimiter
    paused_until: datetime | None = None
    consecutive_failures: int = 0

    def blocked_until(self, session: Session, now: datetime) -> datetime | None:
        """Long blocks only (paused after errors, daily quota used up), not per-minute spacing."""
        times = [self.limiter.quota_reset_at(session, now)]
        if self.paused_until and self.paused_until > now:
            times.append(self.paused_until)
        times = [t for t in times if t is not None]
        return max(times) if times else None


class QueueWorker:
    def __init__(
        self,
        primary: ModelSlot,
        fallback: ModelSlot | None = None,
        batch_size: int | None = None,
        max_attempts: int | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.batch_size = batch_size or settings.summary_batch_size
        self.max_attempts = max_attempts or settings.summary_max_attempts
        # Injected so tests can control time, including time passing during a slow request.
        self.clock = clock

    def run_once(self, session: Session) -> RunResult:
        """Process at most one batch (one Gemini request)."""
        now = self.clock()
        slot, wait_until = self._choose_slot(session, now)
        if slot is None:
            return RunResult(Outcome.WAITING, next_run_at=wait_until)

        articles = self._claim_batch(session, now)
        if not articles:
            return RunResult(Outcome.IDLE)

        model = slot.summarizer.model
        slot.limiter.record_request(session, now)
        inputs = [ArticleInput(a.id, a.title, a.content or a.rss_summary or "") for a in articles]
        try:
            summaries = slot.summarizer.summarize(inputs)
        except TransientSummaryError as exc:
            self._release(session, articles)
            # Pause from when the failure arrived: a timeout may come minutes after `now`.
            self._pause(session, slot, exc, self.clock())
            logger.warning("%s failed (transient): %s", model, exc)
            return RunResult(Outcome.REQUEST_FAILED, model=model, error=str(exc))
        except PermanentSummaryError as exc:
            slot.consecutive_failures = 0
            logger.warning("%s failed (permanent) for %s: %s", model, [a.id for a in articles], exc)
            result = RunResult(Outcome.REQUEST_FAILED, model=model, error=str(exc))
            for article in articles:
                # Only a single-article request proves that the article itself is the problem.
                self._record_failure(article, str(exc), now, result, permanent=len(articles) == 1)
            session.commit()
            return result
        except Exception:
            self._release(session, articles)  # never leave articles stuck in "processing"
            raise

        slot.consecutive_failures = 0
        slot.paused_until = None
        result = RunResult(Outcome.SUMMARIZED, model=model)
        for article in articles:
            summary = summaries.get(article.id)
            if summary is None:
                self._record_failure(article, "Missing from model response", now, result)
            else:
                self._mark_done(article, summary, model, now)
                result.done += 1
        session.commit()
        return result

    def _choose_slot(
        self, session: Session, now: datetime
    ) -> tuple[ModelSlot | None, datetime | None]:
        """Use the main model unless it is blocked for a while; then the fallback.
        Returns (slot, None) to go ahead, or (None, time to try again)."""
        primary_blocked = self.primary.blocked_until(session, now)
        if primary_blocked is None:
            slot = self.primary
        elif self.fallback and self.fallback.blocked_until(session, now) is None:
            slot = self.fallback
        else:
            ends = [primary_blocked]
            if self.fallback:
                ends.append(self.fallback.blocked_until(session, now))
            return None, min(t for t in ends if t is not None)

        spacing = slot.limiter.spacing_wait_until(now)
        return (None, spacing) if spacing else (slot, None)

    def _claim_batch(self, session: Session, now: datetime) -> list[Article]:
        due = select(Article).where(
            Article.summary_status == SummaryStatus.PENDING,
            or_(col(Article.next_attempt_at).is_(None), col(Article.next_attempt_at) <= now),
        )
        # Newest first: if a backlog builds up, today's news gets summarized first.
        newest_first = (col(Article.published_at).desc(), col(Article.id).desc())

        retry = session.exec(
            due.where(Article.summary_attempts > 0).order_by(*newest_first).limit(1)
        ).first()
        if retry:
            articles = [retry]
        else:
            articles = list(
                session.exec(
                    due.where(Article.summary_attempts == 0)
                    .order_by(*newest_first)
                    .limit(self.batch_size)
                ).all()
            )

        for article in articles:
            article.summary_status = SummaryStatus.PROCESSING
            session.add(article)
        session.commit()
        return articles

    def _release(self, session: Session, articles: list[Article]) -> None:
        session.rollback()  # discard anything half-written for this batch
        for article in articles:
            article.summary_status = SummaryStatus.PENDING
            session.add(article)
        session.commit()

    def _pause(
        self, session: Session, slot: ModelSlot, exc: TransientSummaryError, now: datetime
    ) -> None:
        slot.consecutive_failures += 1
        if exc.daily_quota_exhausted:
            slot.limiter.mark_daily_exhausted(session, now)
            return
        if exc.retry_after is not None:
            pause = timedelta(seconds=exc.retry_after)
        else:
            pause = min(PAUSE_BASE * 2 ** (slot.consecutive_failures - 1), MAX_PAUSE)
        slot.paused_until = now + pause

    def _record_failure(
        self,
        article: Article,
        error: str,
        now: datetime,
        result: RunResult,
        permanent: bool = False,
    ) -> None:
        article.summary_attempts += 1
        article.summary_error = error
        if permanent or article.summary_attempts >= self.max_attempts:
            article.summary_status = SummaryStatus.FAILED
            article.next_attempt_at = None
            result.failed += 1
        else:
            article.summary_status = SummaryStatus.PENDING
            article.next_attempt_at = now + RETRY_BACKOFF_BASE * 2 ** (article.summary_attempts - 1)
            result.retrying += 1

    @staticmethod
    def _mark_done(article: Article, summary: ArticleSummary, model: str, now: datetime) -> None:
        article.title_tr = summary.title_tr
        article.summary_tr = summary.summary_tr
        article.key_points = summary.key_points
        article.model_used = model
        article.summarized_at = now
        article.summary_status = SummaryStatus.DONE
        article.summary_error = None
        article.next_attempt_at = None


def reset_stuck_articles(session: Session) -> int:
    """Crash recovery: articles left in "processing" by a killed process go back to pending."""
    result = session.exec(
        update(Article)
        .where(col(Article.summary_status) == SummaryStatus.PROCESSING)
        .values(summary_status=SummaryStatus.PENDING)
    )
    session.commit()
    return result.rowcount


def create_worker() -> QueueWorker:
    primary = ModelSlot(
        summarizer=GeminiSummarizer(model=settings.gemini_model),
        limiter=RateLimiter(
            settings.gemini_model, settings.gemini_rpm, settings.gemini_daily_limit
        ),
    )
    fallback = None
    if settings.gemini_fallback_model:
        fallback = ModelSlot(
            summarizer=GeminiSummarizer(model=settings.gemini_fallback_model),
            limiter=RateLimiter(
                settings.gemini_fallback_model,
                settings.gemini_fallback_rpm,
                settings.gemini_fallback_daily_limit,
            ),
        )
    return QueueWorker(primary, fallback)
