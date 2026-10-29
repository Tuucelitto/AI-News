from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, HTTPException, Response, status
from sqlmodel import Session, col, func, select

from app.api.deps import AdminDep, HttpClientDep, SessionDep
from app.models import Article, Feed, SummaryStatus
from app.schemas import FeedCreate, FeedRead, FeedRefreshResult, FeedUpdate
from app.services.extractor import process_new_articles
from app.services.fetcher import download_feed, fetch_feed, parse_feed

router = APIRouter(prefix="/feeds", tags=["feeds"])


def _get_feed(session: Session, feed_id: int) -> Feed:
    feed = session.get(Feed, feed_id)
    if feed is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Feed not found")
    return feed


def _to_read(session: Session, feed: Feed) -> FeedRead:
    count = session.exec(
        select(func.count()).select_from(Article).where(Article.feed_id == feed.id)
    ).one()
    return FeedRead.model_validate(feed, update={"article_count": count})


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


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[AdminDep])
def create_feed(body: FeedCreate, session: SessionDep, client: HttpClientDep) -> FeedRead:
    """Add a feed after checking that the URL really serves an RSS/Atom feed."""
    url = str(body.url)
    if session.exec(select(Feed).where(Feed.url == url)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "A feed with this URL already exists")

    try:
        parsed = parse_feed(download_feed(client, url))
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Could not download feed: HTTP {exc.response.status_code}",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"Could not download feed: {type(exc).__name__}"
        ) from exc
    if not parsed.entries:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "URL is not a valid RSS/Atom feed"
        )

    feed = Feed(
        name=body.name or parsed.feed.get("title") or urlsplit(url).netloc,
        url=url,
        site_url=parsed.feed.get("link"),
    )
    session.add(feed)
    session.commit()
    session.refresh(feed)
    return _to_read(session, feed)


@router.patch("/{feed_id}", dependencies=[AdminDep])
def update_feed(feed_id: int, body: FeedUpdate, session: SessionDep) -> FeedRead:
    feed = _get_feed(session, feed_id)
    # Only fields the client actually sent; an explicit null is ignored.
    for field, value in body.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(feed, field, value)
    session.add(feed)
    session.commit()
    session.refresh(feed)
    return _to_read(session, feed)


@router.delete("/{feed_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[AdminDep])
def delete_feed(feed_id: int, session: SessionDep) -> Response:
    """Delete a feed and all of its articles."""
    session.delete(_get_feed(session, feed_id))
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{feed_id}/refresh", dependencies=[AdminDep])
def refresh_feed(feed_id: int, session: SessionDep, client: HttpClientDep) -> FeedRefreshResult:
    """Fetch one feed now and extract its new articles. The scheduler summarizes them."""
    feed = _get_feed(session, feed_id)
    result = fetch_feed(client, session, feed)
    counts = process_new_articles(client, session, feed_id=feed_id)
    return FeedRefreshResult(
        new_articles=result.new_articles,
        not_modified=result.not_modified,
        error=result.error,
        queued_for_summary=counts[SummaryStatus.PENDING],
        skipped=counts[SummaryStatus.SKIPPED],
    )
