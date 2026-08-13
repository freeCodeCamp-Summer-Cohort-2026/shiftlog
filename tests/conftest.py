"""Test fixtures.

Tests run against an in-memory SQLite database instead of Postgres, wired in
by overriding the `get_session` dependency. This keeps `pytest` runnable
with zero external services (including in CI) while still exercising the
real SQLModel models and routes.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.database import get_session
from app.main import app
from app.rate_limiter import limiter


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Keep rate-limit counters isolated between tests."""
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    # The background watcher loop runs against app.database.engine (Postgres
    # by default) via the app's lifespan handler; TestClient triggers that
    # lifespan, so it briefly runs against a DB that doesn't exist in CI.
    # That's fine - it only logs a caught exception and keeps polling - but
    # it's noisy, so tests don't rely on it doing anything.
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture(name="worker_id")
def worker_id_fixture(client: TestClient) -> int:
    response = client.post("/workers", json={"name": "Alice Rivera", "role": "Barista"})
    assert response.status_code == 201
    return response.json()["id"]
