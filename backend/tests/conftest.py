import os

# Must be set before importing the app, so tests never touch the real database.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SCHEDULER_ENABLED"] = "false"
# Environment variables win over backend/.env, so tests never see the real API key.
os.environ["GEMINI_API_KEY"] = ""
os.environ["ADMIN_API_KEY"] = "test-admin-key"

from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import event  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from sqlmodel import Session, create_engine  # noqa: E402

from app.db import configure_sqlite_connection, create_tables, get_session  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def session() -> Iterator[Session]:
    # A fresh in-memory database per test. StaticPool reuses a single connection,
    # otherwise every new connection would see an empty in-memory database.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    event.listen(engine, "connect", configure_sqlite_connection)
    create_tables(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    # Endpoints get the test session instead of a real database session.
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()
