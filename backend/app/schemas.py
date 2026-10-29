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


class ArticleDetail(ArticleListItem):
    author: str | None
    key_points: list[str] | None
    model_used: str | None
    summarized_at: datetime | None
