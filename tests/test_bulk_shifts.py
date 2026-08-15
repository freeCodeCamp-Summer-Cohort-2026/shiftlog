from fastapi.testclient import TestClient


def test_bulk_create_all_valid(client: TestClient, worker_id: int):
    response = client.post(
        "/shifts/bulk",
        json=[
            {"worker_id": worker_id, "start_time": "2026-08-10T09:00:00", "end_time": "2026-08-10T12:00:00"},
            {"worker_id": worker_id, "start_time": "2026-08-10T13:00:00", "end_time": "2026-08-10T17:00:00"},
        ],
    )
    assert response.status_code == 201
    body = response.json()
    assert len(body["accepted_shifts"]) == 2
    assert len(body["rejected_shifts"]) == 0


def test_bulk_create_unknown_worker(client: TestClient, worker_id: int):
    response = client.post(
        "/shifts/bulk",
        json=[
            {"worker_id": worker_id, "start_time": "2026-08-10T09:00:00", "end_time": "2026-08-10T12:00:00"},
            {"worker_id": 9999, "start_time": "2026-08-10T09:00:00", "end_time": "2026-08-10T12:00:00"},
        ],
    )
    assert response.status_code == 201
    body = response.json()
    assert len(body["accepted_shifts"]) == 1
    assert len(body["rejected_shifts"]) == 1
    assert "not found" in body["rejected_shifts"][0]["reason"].lower()


def test_bulk_create_conflicts_with_existing_shift(client: TestClient, worker_id: int):
    # Create an initial shift for the worker
    client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-10T09:00:00",
            "end_time": "2026-08-10T12:00:00",
        },
    )

    # Attempt to create a bulk of shifts, one of which conflicts with the existing shift
    response = client.post(
        "/shifts/bulk",
        json=[
            {"worker_id": worker_id, "start_time": "2026-08-10T11:00:00", "end_time": "2026-08-10T14:00:00"},  # Conflicts
            {"worker_id": worker_id, "start_time": "2026-08-10T13:00:00", "end_time": "2026-08-10T17:00:00"},  # Valid
        ],
    )
    assert response.status_code == 201
    body = response.json()
    assert len(body["accepted_shifts"]) == 1
    assert len(body["rejected_shifts"]) == 1
    assert "conflict" in body["rejected_shifts"][0]["reason"].lower()


def test_bulk_create_conflicts_within_batch(client: TestClient, worker_id: int):
    response = client.post(
        "/shifts/bulk",
        json=[
            {"worker_id": worker_id, "start_time": "2026-08-10T09:00:00", "end_time": "2026-08-10T12:00:00"},
            {"worker_id": worker_id, "start_time": "2026-08-10T11:00:00", "end_time": "2026-08-10T14:00:00"},  # Conflicts with the first
        ],
    )
    assert response.status_code == 201
    body = response.json()
    assert len(body["accepted_shifts"]) == 1
    assert len(body["rejected_shifts"]) == 1
    assert body["accepted_shifts"][0]["start_time"].startswith("2026-08-10T09:00:00")
    assert body["rejected_shifts"][0]["shift"]["start_time"].startswith("2026-08-10T11:00:00")
    assert "conflict" in body["rejected_shifts"][0]["reason"].lower()
