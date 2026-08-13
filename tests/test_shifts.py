from fastapi.testclient import TestClient
import time


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


# 
def test_cache_shift(client: TestClient, worker_id: int):

    test_create_shift(client, worker_id)

    first_call = track_get_shift_duration(client, worker_id)
    second_call = track_get_shift_duration(client, worker_id)
    assert second_call < first_call


def track_get_shift_duration(client: TestClient, worker_id: int):
    start_time = time.perf_counter()
    response = client.get("/shifts", params={"worker_id": worker_id})
    end_time = time.perf_counter()
    return end_time - start_time


