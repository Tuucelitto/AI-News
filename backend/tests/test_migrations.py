from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, inspect, text
from sqlmodel import SQLModel

from app.db import alembic_config, build_engine, create_tables, init_db

APP_TABLES = {"feed", "article", "api_usage"}


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    # A real file database: migrations run DDL the way they do in production.
    engine = build_engine(f"sqlite:///{tmp_path / 'test.db'}")
    yield engine
    engine.dispose()


def head_revision() -> str:
    return ScriptDirectory.from_config(alembic_config()).get_current_head()


def current_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def test_migrations_create_the_same_schema_as_the_models(engine: Engine) -> None:
    """Fails when a model changes without a matching migration
    (fix: uv run alembic revision --autogenerate -m "...")."""
    init_db(engine)

    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        differences = compare_metadata(context, SQLModel.metadata)

    assert differences == []
    assert current_revision(engine) == head_revision()


def test_existing_database_is_adopted_without_losing_data(engine: Engine) -> None:
    # A database from before migrations existed, created straight from the models.
    create_tables(engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO feed (name, url, is_active, created_at)"
                " VALUES ('A', 'u', 1, '2026-01-01')"
            )
        )

    init_db(engine)

    assert current_revision(engine) == head_revision()
    with engine.connect() as connection:
        assert connection.execute(text("SELECT name FROM feed")).scalar_one() == "A"


def test_init_db_can_run_repeatedly(engine: Engine) -> None:
    init_db(engine)
    init_db(engine)  # every app start calls it

    assert current_revision(engine) == head_revision()


def test_downgrade_and_upgrade_round_trip(engine: Engine) -> None:
    init_db(engine)
    config = alembic_config()

    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
    assert APP_TABLES.isdisjoint(inspect(engine).get_table_names())

    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    assert APP_TABLES <= set(inspect(engine).get_table_names())
