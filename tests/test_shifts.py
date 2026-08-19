from fastapi.testclient import TestClient
from fastapi import Depends
from sqlmodel import Session
from app.routers.shifts import list_shifts


def test_create_shift(client: TestClient, worker_id: int):
    response = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-10T09:00:00",
            "end_time": "2026-08-10T17:00:00",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["worker_id"] == worker_id
    assert "id" in body
    assert "created_at" in body


def test_create_shift_unknown_worker(client: TestClient):
    response = client.post(
        "/shifts",
        json={
            "worker_id": 9999,
            "start_time": "2026-08-10T09:00:00",
            "end_time": "2026-08-10T17:00:00",
        },
    )
    assert response.status_code == 404


def test_delete_shift(client: TestClient, worker_id: int):
    create = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-10T09:00:00",
            "end_time": "2026-08-10T17:00:00",
        },
    )
    shift_id = create.json()["id"]

    delete_response = client.delete(f"/shifts/{shift_id}")
    assert delete_response.status_code == 204

    get_response = client.get(f"/shifts/{shift_id}")
    assert get_response.status_code == 404


def test_cache_shift(client: TestClient, monkeypatch):
    list_shifts.cache_clear()

    exec_calls = 0
    real_exec = Session.exec

    def exec_spy(self, statement, *args, **kwargs):
        nonlocal exec_calls
        exec_calls += 1
        return real_exec(self, statement, *args, **kwargs)

    monkeypatch.setattr(Session, "exec", exec_spy)

    params = {"worker_id": 1}

    response1 = client.get("/shifts", params=params)
    response2 = client.get("/shifts", params=params)

    assert response1.status_code == 200
    assert response2.status_code == 200

    assert exec_calls == 1



