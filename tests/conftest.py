"""Test fixtures.

Tests run against an in-memory SQLite database instead of Postgres, wired in
by overriding the `get_session` dependency. This keeps `pytest` runnable
with zero external services (including in CI) while still exercising the
real SQLModel models and routes.
"""

import os

# Set JWT_SECRET before loading any application modules
os.environ["JWT_SECRET"] = "ci-local-test-secret-key-that-is-at-least-32-bytes-long!"

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.auth import require_auth
from app.database import get_session
from app.main import app
from app.models import Worker
from app.rate_limiter import limiter
from app.routers.auth import create_access_token


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Keep rate-limit counters isolated between tests."""
    try:
        limiter.reset()
    except Exception:
        pass
    yield
    try:
        limiter.reset()
    except Exception:
        pass


@pytest.fixture(name="session", autouse=True)
def session_fixture():
    """Yield a fresh in-memory SQLite session per test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="client")
def client_fixture(session: Session):
    """Yield a TestClient with database session and authentication dependency overrides."""
    def get_session_override():
        return session

    mock_worker = Worker(id=1, name="Mock Auth Worker", role="Admin")
    # The background watcher loop runs against app.database.engine (Postgres
    # by default) via the app's lifespan handler; TestClient triggers that
    # lifespan, so it briefly runs against a DB that doesn't exist in CI.
    # That's fine - it only logs a caught exception and keeps polling - but
    # it's noisy, so tests don't rely on it doing anything.
    app.dependency_overrides[get_session] = get_session_override
    app.dependency_overrides[require_auth] = lambda: mock_worker

    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture(name="auth_headers")
def auth_headers_fixture() -> dict[str, str]:
    """Generate valid Bearer authorization headers for token verification tests."""
    token = create_access_token(worker_id=1)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(name="worker_id")
def worker_id_fixture(client: TestClient) -> int:
    """Create a default worker and return its database ID."""
    res = client.post(
        "/workers",
        json={"name": "Alice Rivera", "role": "Barista"},
    )
    return res.json()["id"]

