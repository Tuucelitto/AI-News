from pathlib import Path

from sqlmodel import Session, select

from app.models import Feed
from app.seed import seed_feeds


def test_seed_is_idempotent(session: Session, tmp_path: Path) -> None:
    sources = tmp_path / "sources.yaml"
    sources.write_text(
        "sources:\n"
        "  - name: A\n    url: https://a.example.com/rss\n"
        "  - name: B\n    url: https://b.example.com/rss\n",
        encoding="utf-8",
    )

    assert seed_feeds(session, sources) == 2
    assert seed_feeds(session, sources) == 0
    assert len(session.exec(select(Feed)).all()) == 2
