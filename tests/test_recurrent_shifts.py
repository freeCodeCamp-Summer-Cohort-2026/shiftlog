"""
Tests for feature #10, https://github.com/freeCodeCamp-Summer-Cohort-2026/shiftlog/issues/10

#  recurrence pattern (day-of-week + time range + repeat count or end date
# Given a shift_id
# And a recurrence pattern and a limit
# Then create required shifts
# And report invalid and conflicting shifts
"""
from datetime import datetime, timedelta

from fastapi.testclient import TestClient


def test_create_single_shift(client: TestClient, worker_id: int):
    response = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-10T09:00:00",
            "end_time": "2026-08-10T17:00:00",
            "period": None,
            "duration": None,
            "repeat": None,
            "end_date": None
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["worker_id"] == worker_id
    assert "id" in body
    assert "created_at" in body

def test_create_shift_recurrent_no_duration(client: TestClient, worker_id: int):
    response = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-09-10T09:00:00",
            "end_time": "2026-09-10T17:00:00",
            "period": "daily",
            "duration": None,
            "repeat": None,
            "end_date": None
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == ("Cannot schedule recurrent shift with period daily,"
                                         " but without duration, repeat or end date.")

def test_create_shift_recurrent_invalid_period(client: TestClient, worker_id: int):
    response = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-09-10T09:00:00",
            "end_time": "2026-09-10T17:00:00",
            "period": "decennial",
            "duration": "2 months",
            "repeat": None,
            "end_date": None
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (f"Cannot schedule recurrent shift with period decennial,"
                    f" and duration 2 months.")

def test_create_shift_recurrent_invalid_duration(client: TestClient, worker_id: int):
    response = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-09-10T09:00:00",
            "end_time": "2026-09-10T17:00:00",
            "period": "weekly",
            "duration": "2 centuries",
            "repeat": None,
            "end_date": None
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (f"Cannot schedule recurrent shift with period weekly,"
                    f" and duration 2 centuries.")

def test_create_shift_recurring_by_period(client: TestClient, worker_id: int):
    now = datetime.utcnow()
    start_time = (now + timedelta(days=2, hours=5))
    end_time = (now + timedelta(days=2, hours=6))

    response = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "period": "weekly",
            "duration": "2 months"
        },
    )

    # Calculation of last shift end_time for weekly during 2 months
    final_end_time = (end_time + timedelta(weeks=8)).isoformat()
    assert response.status_code == 201
    body = response.json()
    if body:
        print(f"DEBUG: test_create_shift_recurring_by_period end_time={body['end_time']}"
              f" computed={final_end_time}")
    assert body["end_time"] == final_end_time
