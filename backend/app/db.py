from collections.abc import Iterator
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Engine, event, inspect
from sqlalchemy.engine import make_url
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings
from app.search import search_fold


def configure_sqlite_connection(dbapi_connection, _connection_record) -> None:
    """Runs for every new SQLite connection."""
    cursor = dbapi_connection.cursor()
    # WAL lets readers (API requests) and the writer (background jobs) work concurrently.
    cursor.execute("PRAGMA journal_mode=WAL")
    # SQLite ignores foreign keys unless enabled per connection.
    cursor.execute("PRAGMA foreign_keys=ON")
    # Overwrites deleted data with zeros, so a removed article text really leaves the file.
    cursor.execute("PRAGMA secure_delete=ON")
    cursor.close()
    # Makes the Python function callable from SQL as search_fold(column).
    dbapi_connection.create_function("search_fold", 1, search_fold, deterministic=True)


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
        event.listen(engine, "connect", configure_sqlite_connection)

    return engine


engine = build_engine(settings.database_url)


BACKEND_DIR = Path(__file__).resolve().parent.parent


# Databases older than migrations match this schema; later migrations still run on them.
FIRST_REVISION = "c05a5421cbe3"


def alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.attributes["configure_logger"] = False  # keep the app's logging setup
    return config


def init_db(target: Engine = engine) -> None:
    """Bring the database schema up to date by running the Alembic migrations."""
    config = alembic_config()
    with target.begin() as connection:
        config.attributes["connection"] = connection
        app_tables = set(inspect(connection).get_table_names()) - {"alembic_version"}
        has_revision = MigrationContext.configure(connection).get_current_revision() is not None
        if app_tables and not has_revision:
            # A database created with create_all before migrations existed: its schema
            # matches the first migration, so mark it as migrated instead of recreating it.
            command.stamp(config, FIRST_REVISION)
        command.upgrade(config, "head")


def create_tables(target: Engine) -> None:
    """Create all tables directly from the models. Only for tests: fast, no migrations."""
    from app import models  # noqa: F401  (registers the tables on SQLModel.metadata)

    SQLModel.metadata.create_all(target)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
