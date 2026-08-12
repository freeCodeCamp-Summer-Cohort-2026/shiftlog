from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from app.database import get_session
from app.main import app


def test_healthy_connection(client: TestClient):
    response = client.get("/health")
    assert response.json()["status"] == "ok"
    assert response.json()["status_code"] == 200
    assert response.status_code == 200

def test_unhealthy_connection(client: TestClient, monkeypatch):
    mock_session = MagicMock()
    mock_session.execute.side_effect = Exception("Database connection failed")
    
    monkeypatch.setitem(app.dependency_overrides, get_session, lambda: mock_session)
    
    response = client.get("/health")
    assert response.json()["status"] == "error"
    assert response.json()["status_code"] == 503
    assert response.status_code == 503
