from datetime import datetime, timedelta

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


def test_invalid_shift_times_end_equals_start(client: TestClient, worker_id: int):
    response = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-12T09:00:00",
            "end_time": "2026-08-12T09:00:00",
        },
    )
    assert response.status_code == 422
    body = response.json()["detail"][0]["msg"]
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

    delete_response = client.delete(f"/shifts/{shift_id + 9999}")
    assert delete_response.status_code == 404

    get_response = client.get(f"/shifts/{shift_id}")
    assert get_response.status_code == 200


def test_schedule_shift_for_inactive_worker_is_rejected(client: TestClient):
    worker = client.post(
        "/workers", json={"name": "Former Worker", "role": "Cook"}
    ).json()
    client.put(
        f"/workers/{worker['id']}",
        json={"name": worker["name"], "role": worker["role"], "active": False},
    )

    response = client.post(
        "/shifts",
        json={
            "worker_id": worker["id"],
            "start_time": "2026-08-10T09:00:00",
            "end_time": "2026-08-10T17:00:00",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Cannot schedule a shift for an inactive worker"


def test_upcoming_shifts_returns_only_within_window(client: TestClient, worker_id: int):
    now = datetime.utcnow()

    # case 1: inside the window (starts in 10 minutes)
    within_window = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": (now + timedelta(minutes=10)).isoformat(),
            "end_time": (now + timedelta(hours=1)).isoformat(),
        },
    ).json()

    # case 2: outside window (starts in 5 hours)
    out_of_window = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": (now + timedelta(hours=5)).isoformat(),
            "end_time": (now + timedelta(hours=6)).isoformat(),
        },
    ).json()

    response = client.get("/shifts/upcoming?minutes=30")

    assert response.status_code == 200
    ids = [s["id"] for s in response.json()]
    assert within_window["id"] in ids
    assert out_of_window["id"] not in ids


def test_shift_duration(client: TestClient, worker_id: int):
    create = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-10T09:00:00",
            "end_time": "2026-08-10T17:00:00",
        },
    )
    shift_id = create.json()["id"]

    get_response = client.get(f"/shifts/{shift_id}")
    assert get_response.status_code == 200

    data = get_response.json()
    assert data["duration_hours"] == 8.0


def test_create_shift_with_notes(client: TestClient, worker_id: int):
    notes = "Covering for Alex"
    response = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-10T09:00:00",
            "end_time": "2026-08-10T17:00:00",
            "notes": notes,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["notes"] == notes

    get_response = client.get(f"/shifts/{body['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["notes"] == notes


def test_create_shift_without_notes(
    client: TestClient, worker_id: int
):
    response = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-10T09:00:00",
            "end_time": "2026-08-10T17:00:00",
        },
    )

    assert response.status_code == 201
    assert response.json()["notes"] is None


def test_create_shift_rejects_notes_over_max_length(
    client: TestClient, worker_id: int
):
    response = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-10T09:00:00",
            "end_time": "2026-08-10T17:00:00",
            "notes": "x" * 301,
        },
    )

    assert response.status_code == 422
