from datetime import datetime

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import Shift


def test_overlapping_shift_is_rejected(client: TestClient, worker_id: int):
    first = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-10T09:00:00",
            "end_time": "2026-08-10T17:00:00",
        },
    )
    assert first.status_code == 201

    # Overlaps the middle of the first shift.
    second = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-10T12:00:00",
            "end_time": "2026-08-10T20:00:00",
        },
    )
    assert second.status_code == 409
    assert "conflict" in second.json()["detail"].lower()


def test_back_to_back_shifts_are_not_conflicts(client: TestClient, worker_id: int):
    first = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-10T09:00:00",
            "end_time": "2026-08-10T17:00:00",
        },
    )
    assert first.status_code == 201

    # Starts exactly when the first one ends - should be allowed.
    second = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-10T17:00:00",
            "end_time": "2026-08-10T21:00:00",
        },
    )
    assert second.status_code == 201


def test_overlapping_shifts_for_different_workers_are_allowed(client: TestClient):
    alice = client.post("/workers", json={"name": "Alice", "role": "Barista"}).json()
    bilal = client.post("/workers", json={"name": "Bilal", "role": "Cashier"}).json()

    first = client.post(
        "/shifts",
        json={
            "worker_id": alice["id"],
            "start_time": "2026-08-10T09:00:00",
            "end_time": "2026-08-10T17:00:00",
        },
    )
    second = client.post(
        "/shifts",
        json={
            "worker_id": bilal["id"],
            "start_time": "2026-08-10T09:00:00",
            "end_time": "2026-08-10T17:00:00",
        },
    )
    assert first.status_code == 201
    assert second.status_code == 201


def test_conflicts_endpoint_returns_conflicting_shifts(client: TestClient, session: Session, worker_id: int):
    # Insert directly via the session to bypass the conflict check, so we can test the /conflicts endpoint.
    first = Shift(worker_id=worker_id, start_time=datetime(2026, 8, 10, 9, 0), end_time=datetime(2026, 8, 10, 17, 0))
    second = Shift(worker_id=worker_id, start_time=datetime(2026, 8, 10, 12, 0), end_time=datetime(2026, 8, 10, 20, 0))

    session.add(first)
    session.add(second)
    session.commit()

    response = client.get("/shifts/conflicts")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 1
    assert data[0]["worker_id"] == worker_id
    assert len(data[0]["conflicting_shifts"]) == 2


def test_conflicts_endpoint_returns_empty_list_when_no_conflicts(client: TestClient, worker_id: int):
    response = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-10T09:00:00",
            "end_time": "2026-08-10T17:00:00",
        },
    )
    assert response.status_code == 201

    response = client.get("/shifts/conflicts")
    assert response.status_code == 200
    assert response.json() == []


def test_shifts_overlapping_in_absolute_time_different_timezones_conflict(
    client: TestClient, worker_id: int
):
    """Shifts that look non-overlapping in naive wall-clock time but overlap in UTC."""
    # Tokyo (+09:00): 09:00 to 15:00 local -> 00:00 to 06:00 UTC
    first = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-10T09:00:00+09:00",
            "end_time": "2026-08-10T15:00:00+09:00",
        },
    )
    assert first.status_code == 201

    # UTC (+00:00): 01:00 to 04:00 UTC (naive wall clock 01:00-04:00 vs 09:00-15:00 has no overlap)
    # But in absolute UTC time, 01:00-04:00 overlaps within 00:00-06:00 UTC.
    second = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-10T01:00:00Z",
            "end_time": "2026-08-10T04:00:00Z",
        },
    )
    assert second.status_code == 409
    assert "conflict" in second.json()["detail"].lower()


def test_shifts_non_overlapping_in_absolute_time_same_wall_clock_allowed(
    client: TestClient, worker_id: int
):
    """Shifts with identical wall-clock times in different timezones that do not overlap in UTC."""
    # Tokyo (+09:00): 09:00 to 17:00 local -> 00:00 to 08:00 UTC
    first = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-10T09:00:00+09:00",
            "end_time": "2026-08-10T17:00:00+09:00",
        },
    )
    assert first.status_code == 201

    # New York (-04:00): 09:00 to 17:00 local -> 13:00 to 21:00 UTC
    # In naive wall-clock time, both are 09:00-17:00 on the same date.
    # In absolute UTC time, 00:00-08:00 and 13:00-21:00 have a 5 hour separation.
    second = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-10T09:00:00-04:00",
            "end_time": "2026-08-10T17:00:00-04:00",
        },
    )
    assert second.status_code == 201


def test_cross_timezone_back_to_back_shifts_allowed(
    client: TestClient, worker_id: int
):
    """Back-to-back shifts defined in different timezones meeting at the same UTC instant."""
    # New York (-04:00): 08:00 to 16:00 local -> 12:00 to 20:00 UTC
    first = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-10T08:00:00-04:00",
            "end_time": "2026-08-10T16:00:00-04:00",
        },
    )
    assert first.status_code == 201

    # London (+01:00): 21:00 to 01:00(+1) local -> 20:00 UTC to 00:00 UTC next day
    second = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-10T21:00:00+01:00",
            "end_time": "2026-08-11T01:00:00+01:00",
        },
    )
    assert second.status_code == 201
