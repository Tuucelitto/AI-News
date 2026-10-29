from fastapi import APIRouter
from sqlmodel import col, func, select

from app.api.deps import SessionDep
from app.models import Article, Feed
from app.schemas import FeedRead

router = APIRouter(prefix="/feeds", tags=["feeds"])


@router.get("")
def list_feeds(session: SessionDep) -> list[FeedRead]:
    """All feeds with their article counts, alphabetically."""
    rows = session.exec(
        # Outer join, so feeds without any articles are listed too (with count 0).
        select(Feed, func.count(col(Article.id)))
        .join(Article, isouter=True)
        .group_by(col(Feed.id))
        .order_by(col(Feed.name))
    ).all()
    return [FeedRead.model_validate(feed, update={"article_count": count}) for feed, count in rows]
