from pathlib import Path

import yaml
from sqlmodel import Session, select

from app.models import Feed

SOURCES_FILE = Path(__file__).resolve().parent.parent / "sources.yaml"


def load_sources(path: Path = SOURCES_FILE) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as file:
        return yaml.safe_load(file)["sources"]


def seed_feeds(session: Session, path: Path = SOURCES_FILE) -> int:
    """On first start, when there are no feeds at all, add the feeds from sources.yaml.

    After that the database (managed through the API) is the source of truth; otherwise
    a feed deleted through the API would come back on the next startup.
    Returns the number of feeds added.
    """
    if session.exec(select(Feed.id).limit(1)).first() is not None:
        return 0
    new_feeds = [Feed(name=source["name"], url=source["url"]) for source in load_sources(path)]
    session.add_all(new_feeds)
    session.commit()
    return len(new_feeds)
