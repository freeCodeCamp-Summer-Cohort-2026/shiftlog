import csv
from datetime import datetime, timedelta
import io

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
    worker = client.post("/workers", json={"name": "Former Worker", "role": "Cook"}).json()
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


def test_update_shift(client: TestClient, worker_id: int):
    # Create shift
    create = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-10T09:00:00",
            "end_time": "2026-08-10T17:00:00",
        },
    )
    shift_id = create.json()["id"]

    # Update shift
    update_res = client.put(
        f"/shifts/{shift_id}",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-10T10:00:00",
            "end_time": "2026-08-10T18:00:00",
        },
    )
    assert update_res.status_code == 200
    body = update_res.json()
    assert body["start_time"] == "2026-08-10T10:00:00"
    assert body["end_time"] == "2026-08-10T18:00:00"


def test_update_shift_not_found(client: TestClient, worker_id: int):
    response = client.put(
        "/shifts/9999",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-10T10:00:00",
            "end_time": "2026-08-10T18:00:00",
        },
    )
    assert response.status_code == 404


def test_update_shift_conflict(client: TestClient, worker_id: int):
    # Shift 1: 09:00 - 12:00
    shift1 = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-10T09:00:00",
            "end_time": "2026-08-10T12:00:00",
        },
    ).json()

    # Shift 2: 13:00 - 17:00
    shift2 = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-10T13:00:00",
            "end_time": "2026-08-10T17:00:00",
        },
    ).json()

    # Try updating shift 2 to overlap with shift 1 (11:00 - 15:00)
    response = client.put(
        f"/shifts/{shift2['id']}",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-10T11:00:00",
            "end_time": "2026-08-10T15:00:00",
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"] == f"Shift conflicts with existing shift(s) for this worker: {shift1['id']}"


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


def test_create_shift_without_notes(client: TestClient, worker_id: int):
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


def test_create_shift_rejects_notes_over_max_length(client: TestClient, worker_id: int):
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


def test_reject_long_shift(client: TestClient, worker_id: int):
    boundary_response = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-16T06:00:00",
            "end_time": "2026-08-17T06:00:00",
        },
    )
    assert boundary_response.status_code == 201

    over_response = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-17T06:00:00",
            "end_time": "2026-08-18T06:00:01",
        },
    )
    assert over_response.status_code == 422


def test_reject_short_shift(client: TestClient, worker_id: int):
    boundary_response = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-16T06:00:00",
            "end_time": "2026-08-16T06:30:00",
        },
    )
    assert boundary_response.status_code == 201

    under_response = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-17T06:00:00",
            "end_time": "2026-08-17T06:29:00",
        },
    )
    assert under_response.status_code == 422

def test_update_shift_notes(client: TestClient, worker_id: int):
    # Create shift with notes
    create = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-10T09:00:00",
            "end_time": "2026-08-10T17:00:00",
            "notes": "Original notes",
        },
    )
    shift_id = create.json()["id"]

    # Update shift notes
    update_res = client.put(
        f"/shifts/{shift_id}",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-10T09:00:00",
            "end_time": "2026-08-10T17:00:00",
            "notes": "Updated notes",
        },
    )
    assert update_res.status_code == 200
    assert update_res.json()["notes"] == "Updated notes"

    # Verify via GET
    get_res = client.get(f"/shifts/{shift_id}")
    assert get_res.status_code == 200
    assert get_res.json()["notes"] == "Updated notes"


def test_update_shift_inactive_worker(client: TestClient, worker_id: int):
    # Create shift for active worker
    create = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-10T09:00:00",
            "end_time": "2026-08-10T17:00:00",
        },
    )
    shift_id = create.json()["id"]

    # Create a second worker and deactivate them
    worker2 = client.post(
        "/workers", json={"name": "Alex Smith", "role": "Cashier"}
    ).json()
    client.put(
        f"/workers/{worker2['id']}",
        json={"name": worker2["name"], "role": worker2["role"], "active": False},
    )

    # Attempt to assign shift to inactive worker via PUT
    update_res = client.put(
        f"/shifts/{shift_id}",
        json={
            "worker_id": worker2["id"],
            "start_time": "2026-08-10T09:00:00",
            "end_time": "2026-08-10T17:00:00",
        },
    )
    assert update_res.status_code == 400
    assert (
        update_res.json()["detail"]
        == "Cannot schedule a shift for an inactive worker"
    )


def test_shifts_today_includes_shift_starting_today(
    client: TestClient, worker_id: int
):
    # Create a shift:
    today_8am = datetime.utcnow().replace(
        hour=8, minute=0, second=0, microsecond=0
    )

    create_res = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": today_8am.isoformat(),
            "end_time": (today_8am + timedelta(hours=8)).isoformat(),
        },
    )
    assert create_res.status_code == 201
    shift_id = create_res.json()["id"]

    response = client.get("/shifts/today")
    assert response.status_code == 200
    ids = [s["id"] for s in response.json()]
    assert shift_id in ids


def test_shifts_today_excludes_shift_starting_tomorrow(
    client: TestClient, worker_id: int
):
    tomorrow_8am = datetime.utcnow().replace(
        hour=8, minute=0, second=0, microsecond=0
    ) + timedelta(days=1)

    create_res = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": tomorrow_8am.isoformat(),
            "end_time": (tomorrow_8am + timedelta(hours=8)).isoformat(),
        },
    )
    assert create_res.status_code == 201
    shift_id = create_res.json()["id"]

    response = client.get("/shifts/today")
    assert response.status_code == 200
    ids = [s["id"] for s in response.json()]
    assert shift_id not in ids


def test_shifts_today_excludes_shift_starting_yesterday_past_midnight(
    client: TestClient, worker_id: int
):
    yesterday_10pm = datetime.utcnow().replace(
        hour=22, minute=0, second=0, microsecond=0
    ) - timedelta(days=1)

    create_res = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": yesterday_10pm.isoformat(),
            "end_time": (yesterday_10pm + timedelta(hours=8)).isoformat(),
        },
    )
    assert create_res.status_code == 201
    shift_id = create_res.json()["id"]

    response = client.get("/shifts/today")
    assert response.status_code == 200
    ids = [s["id"] for s in response.json()]
    assert shift_id not in ids

