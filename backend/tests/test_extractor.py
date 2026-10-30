from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from sqlmodel import Session, select

from app.models import Article, Feed, SummaryStatus
from app.services.extractor import process_new_articles

LONG_ARTICLE = (Path(__file__).parent / "fixtures" / "article_long.html").read_text()
SHORT_ARTICLE = (
    "<html><body><article><p>OpenAI shipped a small update today.</p></article></body></html>"
)
MIN_CHARS = 1500
BASE_TIME = datetime(2026, 10, 29, 8, 0, tzinfo=UTC)


def handler(request: httpx.Request) -> httpx.Response:
    pages = {"/long": LONG_ARTICLE, "/short": SHORT_ARTICLE}
    if request.url.path in pages:
        return httpx.Response(200, text=pages[request.url.path])
    return httpx.Response(404)


def mock_client() -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def add_article(
    session: Session,
    path: str,
    rss_summary: str | None = None,
    content: str | None = None,
    status: SummaryStatus = SummaryStatus.NEW,
    hours_after_base: int = 0,
) -> Article:
    feed = session.exec(select(Feed)).first()
    if feed is None:
        feed = Feed(name="Example", url="https://news.example.com/rss")
        session.add(feed)
        session.commit()
        session.refresh(feed)

    article = Article(
        feed_id=feed.id,
        guid=path,
        url=f"https://news.example.com{path}",
        title=path,
        rss_summary=rss_summary,
        content=content,
        summary_status=status,
        published_at=BASE_TIME + timedelta(hours=hours_after_base),
    )
    session.add(article)
    session.commit()
    session.refresh(article)
    return article


def run(session: Session, limit: int = 50):
    return process_new_articles(mock_client(), session, limit=limit, delay=0, min_chars=MIN_CHARS)


def test_long_article_is_queued_with_main_text_only(session: Session) -> None:
    article = add_article(session, "/long")

    counts = run(session)

    assert counts[SummaryStatus.PENDING] == 1
    assert article.summary_status == SummaryStatus.PENDING
    assert article.content is not None
    assert "seventy billion parameters" in article.content
    assert "Subscribe to our newsletter" not in article.content  # navigation removed
    assert "All rights reserved" not in article.content  # footer removed
    assert article.content_length == len(article.content) >= MIN_CHARS


def test_short_article_is_skipped(session: Session) -> None:
    article = add_article(session, "/short")

    run(session)

    assert article.summary_status == SummaryStatus.SKIPPED
    assert article.content_length < MIN_CHARS


def test_failed_download_falls_back_to_rss_summary(session: Session) -> None:
    article = add_article(session, "/missing", rss_summary="Short RSS description.")

    run(session)

    assert article.content is None  # skipped: nothing to keep the text for
    assert article.content_length == len("Short RSS description.")
    assert article.summary_status == SummaryStatus.SKIPPED


def test_long_rss_summary_is_enough_when_download_fails(session: Session) -> None:
    article = add_article(session, "/missing", rss_summary="word " * 400)

    run(session)

    assert article.summary_status == SummaryStatus.PENDING


def test_feed_content_is_used_when_download_fails(session: Session) -> None:
    feed_text = "Paragraph from the feed. " * 80  # ~2000 chars, like Ars Technica's feed
    article = add_article(session, "/missing", rss_summary="Teaser.", content=feed_text)

    run(session)

    assert article.content == feed_text
    assert article.summary_status == SummaryStatus.PENDING


def test_longest_text_wins_over_a_shorter_extracted_page(session: Session) -> None:
    feed_text = "Paragraph from the feed. " * 80
    article = add_article(session, "/short", content=feed_text)

    run(session)

    assert article.content == feed_text


def test_failed_download_without_rss_summary_is_skipped(session: Session) -> None:
    article = add_article(session, "/missing")

    run(session)

    assert article.content is None
    assert article.content_length == 0
    assert article.summary_status == SummaryStatus.SKIPPED


def test_only_new_articles_are_processed_oldest_first_up_to_limit(session: Session) -> None:
    done = add_article(session, "/done", status=SummaryStatus.DONE, hours_after_base=0)
    newest = add_article(session, "/long", hours_after_base=3)
    oldest = add_article(session, "/short", hours_after_base=1)
    middle = add_article(session, "/missing", hours_after_base=2)

    counts = run(session, limit=2)

    assert sum(counts.values()) == 2
    assert oldest.summary_status == SummaryStatus.SKIPPED
    assert middle.summary_status == SummaryStatus.SKIPPED
    assert newest.summary_status == SummaryStatus.NEW  # left for the next run
    assert done.summary_status == SummaryStatus.DONE
    assert done.content is None  # untouched
