import os
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from app.auth import  require_auth
from app.routers.auth import create_access_token
from app.database import get_session
from app.main import app
from app.models import Worker
from app.rate_limiter import limiter


@pytest.fixture(name="session", autouse=True)
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    try:
        limiter.reset()
    except Exception:
        pass
    yield
    try:
        limiter.reset()
    except Exception:
        pass


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    mock_worker = Worker(id=1, name="Mock Auth Worker", role="Admin")

    app.dependency_overrides[get_session] = get_session_override
    # Mock require_auth so standard tests don't require DB auth records
    app.dependency_overrides[require_auth] = lambda: mock_worker

    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture(name="auth_headers")
def auth_headers_fixture() -> dict[str, str]:
    os.environ["JWT_SECRET"] = os.getenv(
        "JWT_SECRET", "super_secret_jwt_key_that_is_at_least_32_bytes_long!"
    )
    token = create_access_token(worker_id=1)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(name="worker_id")
def worker_id_fixture(client: TestClient) -> int:
    res = client.post(
        "/workers",
        json={"name": "Default Test Worker", "role": "Cook"},
    )
    return res.json()["id"]