from pathlib import Path

import pytest
from sqlmodel import Session, select

from app.models import Feed
from app.seed import seed_feeds


@pytest.fixture
def sources(tmp_path: Path) -> Path:
    path = tmp_path / "sources.yaml"
    path.write_text(
        "sources:\n"
        "  - name: A\n    url: https://a.example.com/rss\n"
        "  - name: B\n    url: https://b.example.com/rss\n",
        encoding="utf-8",
    )
    return path


def test_seed_fills_an_empty_database_once(session: Session, sources: Path) -> None:
    assert seed_feeds(session, sources) == 2
    assert seed_feeds(session, sources) == 0
    assert len(session.exec(select(Feed)).all()) == 2


def test_seed_does_not_bring_back_deleted_feeds(session: Session, sources: Path) -> None:
    seed_feeds(session, sources)
    session.delete(session.exec(select(Feed).where(Feed.name == "A")).one())
    session.commit()

    assert seed_feeds(session, sources) == 0
    assert [feed.name for feed in session.exec(select(Feed)).all()] == ["B"]
