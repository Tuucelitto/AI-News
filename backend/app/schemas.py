"""API response models. Kept separate from the table models so that internal
fields (like the full extracted `content`) can never leak into a response."""

from datetime import datetime

from pydantic import BaseModel
from sqlmodel import SQLModel

from app.models import SummaryStatus


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    size: int


class FeedRead(SQLModel):
    id: int
    name: str
    url: str
    site_url: str | None
    is_active: bool
    last_fetched_at: datetime | None
    last_error: str | None
    article_count: int


class ArticleListItem(SQLModel):
    id: int
    feed_id: int
    feed_name: str
    title: str
    url: str
    published_at: datetime | None
    title_tr: str | None
    summary_tr: str | None
    rss_summary: str | None
    summary_status: SummaryStatus


class ModelStatus(BaseModel):
    model: str
    role: str  # "primary" or "fallback"
    requests_today: int
    daily_limit: int
    quota_resets_at: datetime
    paused_until: datetime | None


class QueueStatus(BaseModel):
    counts: dict[SummaryStatus, int]
    models: list[ModelStatus]
    scheduler_running: bool
    last_fetch_at: datetime | None
    next_fetch_at: datetime | None


class ArticleDetail(ArticleListItem):
    author: str | None
    key_points: list[str] | None
    model_used: str | None
    summarized_at: datetime | None
