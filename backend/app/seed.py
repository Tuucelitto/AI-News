from pathlib import Path

import yaml
from sqlmodel import Session, select

from app.models import Feed

SOURCES_FILE = Path(__file__).resolve().parent.parent / "sources.yaml"


def load_sources(path: Path = SOURCES_FILE) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as file:
        return yaml.safe_load(file)["sources"]


def seed_feeds(session: Session, path: Path = SOURCES_FILE) -> int:
    """Add feeds from sources.yaml that are not in the database yet.

    Existing feeds are left untouched, so this is safe to run on every startup.
    Returns the number of feeds added.
    """
    existing_urls = set(session.exec(select(Feed.url)).all())
    new_feeds = [
        Feed(name=source["name"], url=source["url"])
        for source in load_sources(path)
        if source["url"] not in existing_urls
    ]
    session.add_all(new_feeds)
    session.commit()
    return len(new_feeds)
