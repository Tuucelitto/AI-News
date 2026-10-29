from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlmodel import Session, select

from app.models import Article, Feed, SummaryStatus
from app.services.fetcher import fetch_all_feeds, fetch_feed, html_to_text, normalize_url

SAMPLE_FEED = (Path(__file__).parent / "fixtures" / "sample_feed.xml").read_bytes()
NOW = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)
MAX_AGE = timedelta(hours=48)

Handler = Callable[[httpx.Request], httpx.Response]


def mock_client(handler: Handler) -> httpx.Client:
    # MockTransport answers requests in-process, so tests never touch the network.
    return httpx.Client(transport=httpx.MockTransport(handler))


def serve_sample(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=SAMPLE_FEED, headers={"content-type": "application/rss+xml"})


def add_feed(session: Session, url: str = "https://blog.example.com/rss") -> Feed:
    feed = Feed(name=url, url=url)
    session.add(feed)
    session.commit()
    session.refresh(feed)
    return feed


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://Example.COM/a?utm_source=x&id=1#top", "https://example.com/a?id=1"),
        ("https://example.com/a?fbclid=abc", "https://example.com/a"),
        ("https://example.com", "https://example.com/"),
        ("  https://example.com/a?b=2&a=1  ", "https://example.com/a?b=2&a=1"),
    ],
)
def test_normalize_url(url: str, expected: str) -> None:
    assert normalize_url(url) == expected


def test_html_to_text() -> None:
    html = "<p>Hello <b>world</b></p><p>Second &amp; last</p>"
    assert html_to_text(html) == "Hello world Second & last"


def test_fetch_stores_only_recent_dated_unique_entries(session: Session) -> None:
    feed = add_feed(session)

    result = fetch_feed(mock_client(serve_sample), session, feed, now=NOW, max_age=MAX_AGE)

    assert result.error is None
    assert result.new_articles == 2
    articles = session.exec(select(Article).order_by(Article.published_at)).all()
    assert [a.url for a in articles] == [
        "https://blog.example.com/yesterday",
        "https://blog.example.com/recent?id=7",
    ]
    recent = articles[1]
    assert recent.title == "Recent story"
    assert recent.rss_summary == "Hello world Second & last"
    assert recent.content == "Full text, first paragraph. Second paragraph."
    assert articles[0].content is None  # no <content:encoded> in that entry
    assert recent.published_at == datetime(2026, 10, 29, 10, 0, tzinfo=UTC)
    assert recent.summary_status == SummaryStatus.NEW
    assert feed.last_fetched_at == NOW
    assert feed.last_error is None


def test_second_fetch_adds_no_duplicates(session: Session) -> None:
    feed = add_feed(session)
    client = mock_client(serve_sample)

    fetch_feed(client, session, feed, now=NOW, max_age=MAX_AGE)
    second = fetch_feed(client, session, feed, now=NOW, max_age=MAX_AGE)

    assert second.new_articles == 0
    assert len(session.exec(select(Article)).all()) == 2


def test_unchanged_feed_is_not_downloaded_again(session: Session) -> None:
    feed = add_feed(session)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.headers.get("If-None-Match") == '"v1"':
            return httpx.Response(304)
        return httpx.Response(200, content=SAMPLE_FEED, headers={"ETag": '"v1"'})

    client = mock_client(handler)
    fetch_feed(client, session, feed, now=NOW, max_age=MAX_AGE)
    second = fetch_feed(client, session, feed, now=NOW, max_age=MAX_AGE)

    assert feed.etag == '"v1"'
    assert second.not_modified
    assert second.error is None


def test_broken_feed_does_not_stop_the_others(session: Session) -> None:
    broken = add_feed(session, "https://broken.example.com/rss")
    invalid = add_feed(session, "https://invalid.example.com/rss")
    good = add_feed(session, "https://blog.example.com/rss")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "broken.example.com":
            return httpx.Response(500)
        if request.url.host == "invalid.example.com":
            return httpx.Response(200, content=b"this is not xml <<<")
        return serve_sample(request)

    results = fetch_all_feeds(mock_client(handler), session, now=NOW)

    assert [r.feed_name for r in results] == [broken.url, invalid.url, good.url]
    assert broken.last_error is not None and "500" in broken.last_error
    assert invalid.last_error is not None and "Invalid feed" in invalid.last_error
    assert good.last_error is None
    assert results[2].new_articles == 2


def test_inactive_feeds_are_skipped(session: Session) -> None:
    feed = add_feed(session)
    feed.is_active = False
    session.commit()

    results = fetch_all_feeds(mock_client(serve_sample), session, now=NOW)

    assert results == []
