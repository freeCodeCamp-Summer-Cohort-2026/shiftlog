from fastapi.testclient import TestClient


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


def test_invalid_shift_times(client: TestClient, worker_id: int):
    response = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-12T17:00:00",
            "end_time": "2026-08-12T09:00:00",
        },
    )
    assert response.status_code == 422
    body = response.json()["detail"][0]["msg"]
    assert "2026-08-12T17:00:00" in body
    assert "2026-08-12T09:00:00" in body
    assert "must be after" in body
    
def test_delete_nonexistent_shift(client: TestClient, worker_id: int):
    create = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-12T09:00:00",
            "end_time": "2026-08-12T17:00:00",
        },
    )
    shift_id = create.json()["id"]

    delete_response = client.delete(f"/shifts/{shift_id+9999}")
    assert delete_response.status_code == 404

    get_response = client.get(f"/shifts/{shift_id}")
    assert get_response.status_code == 200
