from datetime import UTC, date, datetime
from enum import StrEnum

from sqlalchemy import JSON, Column, DateTime, Index, TypeDecorator
from sqlmodel import Field, Relationship, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator):
    """Stores datetimes as UTC and returns them timezone-aware.

    SQLite has no timezone support and returns naive datetimes, which cannot be
    compared with aware ones in Python. This type normalizes both directions.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Naive datetime is not allowed; use timezone-aware UTC values.")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        return value.replace(tzinfo=UTC) if value is not None else None


class SummaryStatus(StrEnum):
    NEW = "new"  # fetched, full text not extracted yet
    PENDING = "pending"  # long enough, waiting in the summary queue
    PROCESSING = "processing"  # picked up by the worker
    DONE = "done"
    SKIPPED = "skipped"  # too short to summarize
    FAILED = "failed"  # permanent error or max attempts reached


class Feed(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    url: str = Field(unique=True)
    site_url: str | None = None
    is_active: bool = True

    # HTTP caching headers from the last fetch, sent back to skip unchanged feeds.
    etag: str | None = None
    modified: str | None = None

    last_fetched_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    last_error: str | None = None
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime)

    articles: list["Article"] = Relationship(back_populates="feed", cascade_delete=True)


class Article(SQLModel, table=True):
    # The worker queries "oldest pending article whose next attempt is due".
    __table_args__ = (Index("ix_article_queue", "summary_status", "next_attempt_at"),)

    id: int | None = Field(default=None, primary_key=True)
    feed_id: int = Field(foreign_key="feed.id", index=True, ondelete="CASCADE")

    guid: str
    url: str = Field(unique=True)  # normalized; used for deduplication
    title: str
    author: str | None = None
    published_at: datetime | None = Field(default=None, index=True, sa_type=UTCDateTime)
    rss_summary: str | None = None

    # Extracted full text. Used only as summarizer input, never exposed by the API.
    content: str | None = None
    content_length: int = 0

    # Gemini output
    title_tr: str | None = None
    summary_tr: str | None = None
    key_points: list[str] | None = Field(default=None, sa_column=Column(JSON))
    model_used: str | None = None
    summarized_at: datetime | None = Field(default=None, sa_type=UTCDateTime)

    # Queue state
    summary_status: SummaryStatus = Field(default=SummaryStatus.NEW)
    summary_attempts: int = 0
    summary_error: str | None = None
    next_attempt_at: datetime | None = Field(default=None, sa_type=UTCDateTime)

    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime)

    feed: Feed | None = Relationship(back_populates="articles")


class ApiUsage(SQLModel, table=True):
    """Number of Gemini requests made per UTC day, for the daily quota."""

    __tablename__ = "api_usage"

    day: date = Field(primary_key=True)
    request_count: int = 0
