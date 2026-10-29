from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, event
from sqlalchemy.engine import make_url
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings


def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    # WAL lets readers (API requests) and the writer (background jobs) work concurrently.
    cursor.execute("PRAGMA journal_mode=WAL")
    # SQLite ignores foreign keys unless enabled per connection.
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def build_engine(database_url: str) -> Engine:
    url = make_url(database_url)
    connect_args = {}

    if url.get_backend_name() == "sqlite":
        # Background jobs run in threads, so connections may cross threads.
        connect_args["check_same_thread"] = False
        if url.database and url.database != ":memory:":
            Path(url.database).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(database_url, connect_args=connect_args)

    if url.get_backend_name() == "sqlite":
        event.listen(engine, "connect", _set_sqlite_pragmas)

    return engine


engine = build_engine(settings.database_url)


def init_db(target: Engine = engine) -> None:
    # Importing models registers the tables on SQLModel.metadata.
    from app import models  # noqa: F401

    SQLModel.metadata.create_all(target)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
