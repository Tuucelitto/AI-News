"""Alembic environment: how migrations connect to the database and what they compare against.

Run from backend/:
    uv run alembic upgrade head                              # apply migrations
    uv run alembic revision --autogenerate -m "add x column" # after changing app/models.py
The app also applies migrations on startup (app.db.init_db).
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy.types import TypeDecorator
from sqlmodel import SQLModel
from sqlmodel.sql.sqltypes import AutoString

from app import models  # noqa: F401  (registers the tables on SQLModel.metadata)
from app.config import settings
from app.db import build_engine

config = context.config

# Skip when called from the app: fileConfig would replace the app's logging setup
# and, by default, silence every logger that already exists.
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def render_item(type_: str, obj, autogen_context) -> str | bool:
    """Write portable SQLAlchemy types into migration files instead of app/SQLModel types,
    so old migrations never import app code that may change later."""
    if type_ == "type":
        if isinstance(obj, AutoString):
            return "sa.String()"
        if isinstance(obj, TypeDecorator):  # e.g. UTCDateTime: only the Python side differs
            return f"sa.{type(obj.impl).__name__}()"  # the stored type, e.g. sa.DateTime()
    return False  # default rendering


def database_url() -> str:
    # The app's settings (backend/.env) are the single source of the URL;
    # tests may override it with config.set_main_option("sqlalchemy.url", ...).
    return config.get_main_option("sqlalchemy.url") or settings.database_url


def configure(**kwargs) -> None:
    context.configure(
        target_metadata=target_metadata,
        # SQLite cannot ALTER most things; batch mode copies the table with the new schema.
        render_as_batch=True,
        compare_type=True,
        render_item=render_item,
        **kwargs,
    )


def run_migrations_offline() -> None:
    """Print the SQL instead of running it (alembic upgrade head --sql)."""
    configure(url=database_url(), literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # The app passes its own connection (see app.db.init_db); the CLI opens one.
    connection = config.attributes.get("connection")
    if connection is not None:
        configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
        return

    engine = build_engine(database_url())
    with engine.connect() as connection:
        configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
