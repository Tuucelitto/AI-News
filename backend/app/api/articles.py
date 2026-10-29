from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.orm import defer
from sqlmodel import col, func, or_, select

from app.api.deps import SessionDep
from app.models import Article, Feed, SummaryStatus, utc_now
from app.schemas import ArticleDetail, ArticleListItem, Page

router = APIRouter(prefix="/articles", tags=["articles"])


@router.get("")
def list_articles(
    session: SessionDep,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    feed_id: int | None = None,
    status: SummaryStatus | None = None,
    q: Annotated[str | None, Query(min_length=2, max_length=100)] = None,
    since_hours: Annotated[int | None, Query(ge=1, le=24 * 30)] = None,
) -> Page[ArticleListItem]:
    """Articles, newest first."""
    filters = []
    if feed_id is not None:
        filters.append(Article.feed_id == feed_id)
    if status is not None:
        filters.append(Article.summary_status == status)
    if since_hours is not None:
        filters.append(col(Article.published_at) >= utc_now() - timedelta(hours=since_hours))
    if q:
        # autoescape makes "%" and "_" in the query match literally instead of as wildcards.
        filters.append(
            or_(
                *(
                    col(field).icontains(q, autoescape=True)
                    for field in (
                        Article.title,
                        Article.title_tr,
                        Article.summary_tr,
                        Article.rss_summary,
                    )
                )
            )
        )

    total = session.exec(select(func.count()).select_from(Article).where(*filters)).one()
    rows = session.exec(
        # One JOIN for the feed names instead of one extra query per article (N+1).
        select(Article, Feed.name)
        .join(Feed)
        .where(*filters)
        .options(defer(Article.content))  # the full text can be large and is never returned
        .order_by(col(Article.published_at).desc(), col(Article.id).desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()

    items = [
        ArticleListItem.model_validate(article, update={"feed_name": feed_name})
        for article, feed_name in rows
    ]
    return Page(items=items, total=total, page=page, size=size)


@router.get("/{article_id}")
def get_article(article_id: int, session: SessionDep) -> ArticleDetail:
    row = session.exec(
        select(Article, Feed.name).join(Feed).where(Article.id == article_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Article not found")

    article, feed_name = row
    return ArticleDetail.model_validate(article, update={"feed_name": feed_name})
