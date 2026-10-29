"""Per-model request limits for the Gemini free tier.

- Requests per minute: enforced as a minimum gap between requests, kept in memory.
  After a restart the first request may come early; a 429 would then pause the worker.
- Requests per day: counted in the database so the count survives restarts.
  Google resets daily quotas at midnight Pacific time, so "day" means a Pacific date.
"""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlmodel import Session

from app.models import ApiUsage

QUOTA_TIMEZONE = ZoneInfo("America/Los_Angeles")


def quota_day(now: datetime) -> date:
    return now.astimezone(QUOTA_TIMEZONE).date()


def next_quota_reset(now: datetime) -> datetime:
    tomorrow = quota_day(now) + timedelta(days=1)
    return datetime.combine(tomorrow, time.min, tzinfo=QUOTA_TIMEZONE).astimezone(UTC)


class RateLimiter:
    def __init__(self, model: str, rpm: int, daily_limit: int) -> None:
        self.model = model
        self.min_interval = timedelta(seconds=60 / rpm)
        self.daily_limit = daily_limit
        self.last_request_at: datetime | None = None

    def _usage(self, session: Session, now: datetime) -> ApiUsage | None:
        return session.get(ApiUsage, (quota_day(now), self.model))

    def requests_today(self, session: Session, now: datetime) -> int:
        usage = self._usage(session, now)
        return usage.request_count if usage else 0

    def quota_reset_at(self, session: Session, now: datetime) -> datetime | None:
        """When the daily quota is used up, the time it resets; otherwise None."""
        if self.requests_today(session, now) >= self.daily_limit:
            return next_quota_reset(now)
        return None

    def spacing_wait_until(self, now: datetime) -> datetime | None:
        """If the previous request was too recent, the earliest time for the next one."""
        if self.last_request_at is None:
            return None
        allowed_at = self.last_request_at + self.min_interval
        return allowed_at if allowed_at > now else None

    def record_request(self, session: Session, now: datetime) -> None:
        # Counted before the call and even if it fails: Google may count failed requests too.
        usage = self._usage(session, now) or ApiUsage(day=quota_day(now), model=self.model)
        usage.request_count += 1
        session.add(usage)
        session.commit()
        self.last_request_at = now

    def mark_daily_exhausted(self, session: Session, now: datetime) -> None:
        """Google said the daily quota is gone; sync our counter so we stop until the reset."""
        usage = self._usage(session, now) or ApiUsage(day=quota_day(now), model=self.model)
        usage.request_count = max(usage.request_count, self.daily_limit)
        session.add(usage)
        session.commit()
