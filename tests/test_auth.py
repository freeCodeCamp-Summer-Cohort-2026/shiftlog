import os
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.auth import require_auth
from app.main import app
from app.models import Worker


def test_register(client: TestClient):
    response = client.post(
        "/auth/register",
        json={
            "username": "register_test_user",
            "password": "password123",
            "name": "Register Test",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "token" in data
    assert "worker" in data
    assert data["worker"]["name"] == "Register Test"
    assert data["worker"]["role"] == "Worker"
    assert "id" in data["worker"]


def test_duplicate_username(client: TestClient):
    client.post(
        "/auth/register",
        json={
            "username": "dup_user",
            "password": "password123",
            "name": "First User",
        },
    )

    response = client.post(
        "/auth/register",
        json={
            "username": "dup_user",
            "password": "password123",
            "name": "Second User",
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Username already exists"


def test_login_success(client: TestClient):
    client.post(
        "/auth/register",
        json={
            "username": "login_user",
            "password": "password123",
            "name": "Login User",
        },
    )

    response = client.post(
        "/auth/login",
        json={
            "username": "login_user",
            "password": "password123",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert "worker" in data
    assert data["worker"]["username"] == "login_user"


def test_login_wrong_password(client: TestClient):
    client.post(
        "/auth/register",
        json={
            "username": "wrong_pwd_user",
            "password": "correctpassword",
            "name": "Wrong Pwd User",
        },
    )

    response = client.post(
        "/auth/login",
        json={
            "username": "wrong_pwd_user",
            "password": "wrongpassword",
        },
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"


def test_protected_endpoints_reject_without_token(client: TestClient):
    # Temporarily remove override to test the real require_auth dependency
    override = app.dependency_overrides.pop(require_auth, None)
    try:
        res_worker = client.post("/workers", json={"name": "No Auth", "role": "Cook"})
        assert res_worker.status_code == 401

        now = datetime.now(timezone.utc)
        res_shift = client.post(
            "/shifts",
            json={
                "worker_id": 1,
                "start_time": now.isoformat(),
                "end_time": (now + timedelta(hours=4)).isoformat(),
            },
        )
        assert res_shift.status_code == 401
    finally:
        if override:
            app.dependency_overrides[require_auth] = override


def test_protected_endpoints_allow_with_valid_token(client: TestClient):
    # Register real worker to receive a real token
    reg = client.post(
        "/auth/register",
        json={
            "username": "valid_token_user",
            "password": "password123",
            "name": "Token User",
        },
    )
    token = reg.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Temporarily remove override to test the real require_auth dependency
    override = app.dependency_overrides.pop(require_auth, None)
    try:
        res_worker = client.post(
            "/workers",
            json={"name": "Protected Worker", "role": "Cashier"},
            headers=headers,
        )
        assert res_worker.status_code == 201
        worker_id = res_worker.json()["id"]

        now = datetime.now(timezone.utc)
        res_shift = client.post(
            "/shifts",
            json={
                "worker_id": worker_id,
                "start_time": now.isoformat(),
                "end_time": (now + timedelta(hours=4)).isoformat(),
            },
            headers=headers,
        )
        assert res_shift.status_code == 201
        shift_id = res_shift.json()["id"]

        assert client.delete(f"/shifts/{shift_id}", headers=headers).status_code == 204
        assert client.delete(f"/workers/{worker_id}", headers=headers).status_code == 204
    finally:
        if override:
            app.dependency_overrides[require_auth] = override
            
