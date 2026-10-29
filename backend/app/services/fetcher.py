"""Download RSS feeds and store new, recent articles."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import feedparser
import httpx
from sqlmodel import Session, col, select

from app.config import settings
from app.models import Article, Feed, utc_now

logger = logging.getLogger(__name__)

USER_AGENT = "ai-news-bot/0.1 (personal RSS reader)"
TIMEOUT_SECONDS = 10
TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid"}
BLOCK_TAGS = {"p", "br", "div", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote"}


@dataclass
class FetchResult:
    feed_name: str
    new_articles: int = 0
    not_modified: bool = False
    error: str | None = None


def create_http_client() -> httpx.Client:
    # feedparser can download feeds itself, but it has no timeout:
    # an unresponsive server could block the whole job forever.
    return httpx.Client(
        timeout=TIMEOUT_SECONDS, follow_redirects=True, headers={"User-Agent": USER_AGENT}
    )


def download_feed(
    client: httpx.Client, url: str, etag: str | None = None, modified: str | None = None
) -> httpx.Response:
    """GET a feed with conditional headers. A 304 response means "unchanged"."""
    headers = {}
    if etag:
        headers["If-None-Match"] = etag
    if modified:
        headers["If-Modified-Since"] = modified

    response = client.get(url, headers=headers)
    if response.status_code != httpx.codes.NOT_MODIFIED:
        response.raise_for_status()
    return response


def parse_feed(response: httpx.Response) -> feedparser.FeedParserDict:
    # Passing the content type lets feedparser pick the right text encoding.
    return feedparser.parse(
        response.content,
        response_headers={"content-type": response.headers.get("content-type", "")},
    )


def entry_date(entry: feedparser.FeedParserDict) -> datetime | None:
    # feedparser normalizes dates to a UTC time.struct_time.
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed is None:
        return None
    return datetime(*parsed[:6], tzinfo=UTC)


def normalize_url(url: str) -> str:
    """Canonical form of an article URL, so the same story is stored only once."""
    parts = urlsplit(url.strip())
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.startswith("utm_") and key not in TRACKING_PARAMS
    ]
    # The fragment (#...) never changes the page, so it is dropped.
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", urlencode(query), "")
    )


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()  # convert_charrefs=True decodes entities like &amp;
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in BLOCK_TAGS:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in BLOCK_TAGS:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    return " ".join("".join(parser.parts).split())


def entry_content(entry: feedparser.FeedParserDict) -> str | None:
    """Full text some feeds embed in <content:encoded>, as plain text."""
    texts = [html_to_text(item.get("value", "")) for item in entry.get("content", [])]
    return max(texts, key=len, default="") or None


def _store_new_entries(
    session: Session, feed: Feed, entries: list[feedparser.FeedParserDict], cutoff: datetime
) -> int:
    candidates: dict[str, Article] = {}
    for entry in entries:
        link = entry.get("link")
        published = entry_date(entry)
        # Undated entries are skipped too: otherwise an archive feed without
        # dates could flood the summary queue.
        if not link or published is None or published < cutoff:
            continue

        url = normalize_url(link)
        candidates.setdefault(
            url,
            Article(
                feed_id=feed.id,
                guid=entry.get("id") or link,
                url=url,
                title=html_to_text(entry.get("title", "")) or "(untitled)",
                author=entry.get("author"),
                published_at=published,
                rss_summary=html_to_text(entry.get("summary", "")) or None,
                content=entry_content(entry),
            ),
        )

    if not candidates:
        return 0

    existing_urls = set(
        session.exec(select(Article.url).where(col(Article.url).in_(candidates))).all()
    )
    new_articles = [article for url, article in candidates.items() if url not in existing_urls]
    session.add_all(new_articles)
    return len(new_articles)


def fetch_feed(
    client: httpx.Client,
    session: Session,
    feed: Feed,
    now: datetime | None = None,
    max_age: timedelta | None = None,
) -> FetchResult:
    """Fetch one feed and store its new articles. Never raises; errors go to feed.last_error."""
    now = now or utc_now()
    max_age = max_age or timedelta(hours=settings.fetch_max_age_hours)
    result = FetchResult(feed.name)

    try:
        response = download_feed(client, feed.url, feed.etag, feed.modified)
        if response.status_code == httpx.codes.NOT_MODIFIED:
            result.not_modified = True
        else:
            parsed = parse_feed(response)
            if parsed.bozo and not parsed.entries:
                raise ValueError(f"Invalid feed: {parsed.bozo_exception}")
            result.new_articles = _store_new_entries(session, feed, parsed.entries, now - max_age)
            feed.etag = response.headers.get("etag")
            feed.modified = response.headers.get("last-modified")
        feed.last_error = None
    except Exception as exc:  # one broken feed must not stop the others
        session.rollback()  # drop any articles added before the error
        result.error = f"{type(exc).__name__}: {exc}"
        feed.last_error = result.error
        logger.warning("Fetching %s failed: %s", feed.name, result.error)

    feed.last_fetched_at = now
    session.add(feed)
    session.commit()
    return result


def fetch_all_feeds(
    client: httpx.Client, session: Session, now: datetime | None = None
) -> list[FetchResult]:
    feeds = session.exec(select(Feed).where(col(Feed.is_active)).order_by(col(Feed.id))).all()
    return [fetch_feed(client, session, feed, now) for feed in feeds]
