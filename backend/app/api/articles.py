from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from fastapi import status as http_status  # `status` is also a query parameter below
from sqlalchemy import String
from sqlalchemy.orm import defer
from sqlmodel import col, func, or_, select

from app.api.deps import AdminDep, SessionDep
from app.models import Article, Feed, SummaryStatus, utc_now
from app.schemas import ArticleDetail, ArticleListItem, Page
from app.search import search_fold

router = APIRouter(prefix="/articles", tags=["articles"])

RESUMMARIZABLE = {SummaryStatus.DONE, SummaryStatus.FAILED, SummaryStatus.SKIPPED}


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
        # Both sides are folded (İ/I/ı → i, accents dropped) so Turkish and English match;
        # see app/search.py. autoescape makes "%" and "_" in the query match literally.
        folded = search_fold(q)
        filters.append(
            or_(
                *(
                    func.search_fold(field, type_=String).contains(folded, autoescape=True)
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


@router.post("/{article_id}/resummarize", dependencies=[AdminDep])
def resummarize_article(article_id: int, session: SessionDep) -> ArticleDetail:
    """Put a finished, failed or skipped article back into the summary queue."""
    article = session.get(Article, article_id)
    if article is None:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, "Article not found")
    if article.summary_status not in RESUMMARIZABLE:
        raise HTTPException(
            http_status.HTTP_409_CONFLICT,
            f"Article is {article.summary_status.value}, not finished",
        )

    article.summary_status = SummaryStatus.PENDING
    article.summary_attempts = 0
    article.summary_error = None
    article.next_attempt_at = None
    session.add(article)
    session.commit()
    return get_article(article_id, session)


@router.get("/{article_id}")
def get_article(article_id: int, session: SessionDep) -> ArticleDetail:
    row = session.exec(
        select(Article, Feed.name).join(Feed).where(Article.id == article_id)
    ).first()
    if row is None:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, "Article not found")

    article, feed_name = row
    return ArticleDetail.model_validate(article, update={"feed_name": feed_name})
