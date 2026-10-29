from datetime import UTC, date, datetime, timedelta

from sqlmodel import Session

from app.services.rate_limiter import RateLimiter, next_quota_reset, quota_day

# 12:00 UTC = 05:00 in California (PDT, UTC-7, until 1 November 2026)
NOW = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)


def test_quota_day_follows_pacific_time() -> None:
    assert quota_day(datetime(2026, 10, 30, 6, 59, tzinfo=UTC)) == date(2026, 10, 29)
    assert quota_day(datetime(2026, 10, 30, 7, 0, tzinfo=UTC)) == date(2026, 10, 30)


def test_next_quota_reset_is_pacific_midnight() -> None:
    assert next_quota_reset(NOW) == datetime(2026, 10, 31, 7, 0, tzinfo=UTC)
    # After the DST switch on 1 November, Pacific midnight is 08:00 UTC.
    assert next_quota_reset(datetime(2026, 11, 2, 12, 0, tzinfo=UTC)) == datetime(
        2026, 11, 3, 8, 0, tzinfo=UTC
    )


def test_requests_are_spaced_by_rpm() -> None:
    limiter = RateLimiter("model", rpm=4, daily_limit=10)  # one request per 15 s
    assert limiter.spacing_wait_until(NOW) is None

    limiter.last_request_at = NOW

    assert limiter.spacing_wait_until(NOW + timedelta(seconds=10)) == NOW + timedelta(seconds=15)
    assert limiter.spacing_wait_until(NOW + timedelta(seconds=15)) is None


def test_daily_limit_blocks_until_reset(session: Session) -> None:
    limiter = RateLimiter("model", rpm=60, daily_limit=2)

    limiter.record_request(session, NOW)
    assert limiter.quota_reset_at(session, NOW) is None
    limiter.record_request(session, NOW)

    assert limiter.requests_today(session, NOW) == 2
    assert limiter.quota_reset_at(session, NOW) == datetime(2026, 10, 31, 7, 0, tzinfo=UTC)
    # A new Pacific day starts with a fresh count.
    assert limiter.requests_today(session, NOW + timedelta(days=1)) == 0


def test_each_model_has_its_own_counter(session: Session) -> None:
    flash = RateLimiter("flash", rpm=60, daily_limit=2)
    lite = RateLimiter("lite", rpm=60, daily_limit=2)

    flash.record_request(session, NOW)
    flash.record_request(session, NOW)

    assert flash.quota_reset_at(session, NOW) is not None
    assert lite.requests_today(session, NOW) == 0


def test_mark_daily_exhausted(session: Session) -> None:
    limiter = RateLimiter("model", rpm=60, daily_limit=18)
    limiter.record_request(session, NOW)

    limiter.mark_daily_exhausted(session, NOW)

    assert limiter.requests_today(session, NOW) == 18
    assert limiter.quota_reset_at(session, NOW) is not None
