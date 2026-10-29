from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError, StatementError
from sqlmodel import Session, select

from app.models import Article, Feed, SummaryStatus


def _feed(session: Session) -> Feed:
    feed = Feed(name="Example", url="https://example.com/rss")
    session.add(feed)
    session.commit()
    session.refresh(feed)
    return feed


def test_article_defaults(session: Session) -> None:
    feed = _feed(session)
    article = Article(feed_id=feed.id, guid="1", url="https://example.com/a", title="A")
    session.add(article)
    session.commit()
    session.refresh(article)

    assert article.summary_status == SummaryStatus.NEW
    assert article.summary_attempts == 0
    assert article.created_at.tzinfo is not None


def test_datetimes_round_trip_as_utc(session: Session) -> None:
    feed = _feed(session)
    published = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    session.add(
        Article(
            feed_id=feed.id,
            guid="1",
            url="https://example.com/a",
            title="A",
            published_at=published,
        )
    )
    session.commit()
    session.expire_all()

    stored = session.exec(select(Article)).one()
    assert stored.published_at == published


def test_naive_datetime_is_rejected(session: Session) -> None:
    feed = _feed(session)
    session.add(
        Article(
            feed_id=feed.id,
            guid="1",
            url="https://example.com/a",
            title="A",
            published_at=datetime(2026, 1, 1),
        )
    )
    with pytest.raises(StatementError, match="Naive datetime"):
        session.commit()


def test_article_url_is_unique(session: Session) -> None:
    feed = _feed(session)
    session.add(Article(feed_id=feed.id, guid="1", url="https://example.com/a", title="A"))
    session.add(Article(feed_id=feed.id, guid="2", url="https://example.com/a", title="A again"))

    with pytest.raises(IntegrityError):
        session.commit()


def test_deleting_feed_deletes_its_articles(session: Session) -> None:
    feed = _feed(session)
    session.add(Article(feed_id=feed.id, guid="1", url="https://example.com/a", title="A"))
    session.commit()

    session.delete(feed)
    session.commit()

    assert session.exec(select(Article)).all() == []
