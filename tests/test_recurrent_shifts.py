"""
Tests for feature #10, https://github.com/freeCodeCamp-Summer-Cohort-2026/shiftlog/issues/10

#  recurrence pattern (day-of-week + time range + repeat count or end date
# Given a shift_id
# And a recurrence pattern and a limit
# Then create required shifts
# And report invalid and conflicting shifts
"""
from datetime import datetime, timedelta, UTC

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
    now = datetime.now(UTC)
    start_time = (now + timedelta(days=2, hours=5))
    end_time = (now + timedelta(days=2, hours=6))

    # List of initial shifts
    get_response = client.get(f"/shifts?worker_id={worker_id}")
    assert get_response.status_code == 200

    data = get_response.json()
    assert len(data) == 0  # Empty shifts

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

    # List of created shifts
    get_response = client.get(f"/shifts?worker_id={worker_id}")
    assert get_response.status_code == 200

    data = get_response.json()
    assert len(data) == 9  # Initial shift plus eight added

def test_create_shift_recurring_by_period_with_conflict(client: TestClient, worker_id: int):
    now = datetime.now(UTC)
    start_time = (now + timedelta(days=9, hours=1))
    end_time = (now + timedelta(days=9, hours=8))

    # Create a shift in the middle of future recurrent
    response = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        },
    )
    assert response.status_code == 201

    start_time = (now + timedelta(days=30, hours=1))
    end_time = (now + timedelta(days=30, hours=8))

    # Create another shift in the middle of future recurrent
    response = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        },
    )
    assert response.status_code == 201

    # List of initial shifts
    get_response = client.get(f"/shifts?worker_id={worker_id}")
    assert get_response.status_code == 200

    data = get_response.json()
    assert len(data) == 2  # existing shifts inside recurrent window

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

    # List of created shifts
    get_response = client.get(f"/shifts?worker_id={worker_id}")
    assert get_response.status_code == 200

    data = get_response.json()
    print(f"DEBUG: test_create_shift_recurring_by_period_with_conflict len data={len(data)}")
    assert len(data) == 9  # Existing two shifts, plus initial and six added

def test_create_shift_recurring_by_period_week_day_mondays(client: TestClient, worker_id: int):
    now = datetime.now(UTC)
    # This week day is variable, so we add this and start recurrence on
    # the next matching week day
    start_time = (now + timedelta(days=2, hours=2))
    end_time = (now + timedelta(days=2, hours=6))

    # List of initial shifts
    get_response = client.get(f"/shifts?worker_id={worker_id}")
    assert get_response.status_code == 200

    data = get_response.json()
    assert len(data) == 0  # Empty shifts

    response = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "period": "Mondays",
            "duration": "4 weeks"
        },
    )

    assert response.status_code == 201

    # List of created shifts
    get_response = client.get(f"/shifts?worker_id={worker_id}")
    assert get_response.status_code == 200

    data = get_response.json()
    assert len(data) == 5  # Initial shift plus four added

    # Confirm that week day of the last shift is the requested, Monday
    assert datetime.fromisoformat(data[-1]['start_time']).weekday() == 0
    print(f"DEBUG: test_create_shift_recurring_by_period_week_day list of shifts"
          f" data={data}")

def test_create_shift_recurring_by_period_week_day_thursday(client: TestClient, worker_id: int):
    # This week day is known, matching our period, so we start recurrence on
    # this week day
    start_time = datetime.fromisoformat("2026-10-01T08:00:00")  # Thursday
    end_time = datetime.fromisoformat("2026-10-01T16:00:00")

    # List of initial shifts
    get_response = client.get(f"/shifts?worker_id={worker_id}")
    assert get_response.status_code == 200

    data = get_response.json()
    assert len(data) == 0  # Empty shifts

    response = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "period": "Thursday",
            "duration": "4 weeks"
        },
    )

    print(f"DEBUG: test_create_shift_recurring_by_period_week_day response={response.json()}")
    # Calculation of the day of the week
    start_week_day = start_time.weekday()
    assert start_week_day == 3  # Thursdays
    assert response.status_code == 201

    # List of created shifts
    get_response = client.get(f"/shifts?worker_id={worker_id}")
    assert get_response.status_code == 200

    data = get_response.json()
    assert len(data) == 5  # Initial shift plus four added

    # Confirm that week day of the last shift is the requested, Thursday
    assert datetime.fromisoformat(data[-1]['start_time']).weekday() == 3
    print(f"DEBUG: test_create_shift_recurring_by_period_week_day list of shifts"
          f" data={data}")


def test_create_shift_recurring_by_period_week_day_saturday(client: TestClient, worker_id: int):
    # This week day is known, matching our period, so we start recurrence on
    # this week day
    start_time = datetime.fromisoformat("2026-10-03T08:00:00")  # Saturday
    end_time = datetime.fromisoformat("2026-10-03T16:00:00")

    # List of initial shifts
    get_response = client.get(f"/shifts?worker_id={worker_id}")
    assert get_response.status_code == 200

    data = get_response.json()
    assert len(data) == 0  # Empty shifts

    response = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "period": "Saturdays",
            "duration": "6 weeks"
        },
    )

    print(f"DEBUG: test_create_shift_recurring_by_period_week_day response={response.json()}")
    # Calculation of the day of the week
    start_week_day = start_time.weekday()
    assert start_week_day == 5  # Saturdays
    assert response.status_code == 201

    # List of created shifts
    get_response = client.get(f"/shifts?worker_id={worker_id}")
    assert get_response.status_code == 200

    data = get_response.json()
    assert len(data) == 7  # Initial shift plus six added

    # Confirm that week day of the last shift is the requested, Saturday
    assert datetime.fromisoformat(data[-1]['start_time']).weekday() == 5
    print(f"DEBUG: test_create_shift_recurring_by_period_week_day list of shifts"
          f" data={data}")

def test_create_shift_recurring_daily_repeat(client: TestClient, worker_id: int):
    now = datetime.now(UTC)
    start_time = (now + timedelta(days=2, hours=1))
    end_time = (now + timedelta(days=2, hours=7))

    # List of initial shifts
    get_response = client.get(f"/shifts?worker_id={worker_id}")
    assert get_response.status_code == 200

    data = get_response.json()
    assert len(data) == 0  # Empty shifts

    response = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "period": "1 day",
            "repeat": 10
        },
    )

    # Calculation of last shift end_time for daily with 10 repetitions
    final_end_time = (end_time + timedelta(days=10)).isoformat()
    assert response.status_code == 201
    body = response.json()
    if body:
        print(f"DEBUG: test_create_shift_recurring_daily_repeat end_time={body['end_time']}"
              f" computed={final_end_time}")
    assert body["end_time"] == final_end_time

    # List of created shifts
    get_response = client.get(f"/shifts?worker_id={worker_id}")
    assert get_response.status_code == 200

    data = get_response.json()
    assert len(data) == 11  # Initial shift plus ten added

def test_create_shift_recurring_weekly_repeat(client: TestClient, worker_id: int):
    now = datetime.now(UTC)
    start_time = (now + timedelta(days=2, hours=1))
    end_time = (now + timedelta(days=2, hours=7))

    # List of initial shifts
    get_response = client.get(f"/shifts?worker_id={worker_id}")
    assert get_response.status_code == 200

    data = get_response.json()
    assert len(data) == 0  # Empty shifts

    response = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "period": "weekly",
            "repeat": 4
        },
    )

    # Calculation of last shift end_time for weekly with 4 repetitions
    final_end_time = (end_time + timedelta(weeks=4)).isoformat()
    assert response.status_code == 201
    body = response.json()
    if body:
        print(f"DEBUG: test_create_shift_recurring_daily_repeat end_time={body['end_time']}"
              f" computed={final_end_time}")
    assert body["end_time"] == final_end_time

    # List of created shifts
    get_response = client.get(f"/shifts?worker_id={worker_id}")
    assert get_response.status_code == 200

    data = get_response.json()
    assert len(data) == 5  # Initial shift plus 4 weeks added

def test_create_shift_recurring_monthly_repeat(client: TestClient, worker_id: int):
    now = datetime.now(UTC)
    start_time = (now + timedelta(days=2, hours=1))
    end_time = (now + timedelta(days=2, hours=7))

    # List of initial shifts
    get_response = client.get(f"/shifts?worker_id={worker_id}")
    assert get_response.status_code == 200

    data = get_response.json()
    assert len(data) == 0  # Empty shifts

    response = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "period": "monthly",
            "repeat": 3
        },
    )

    # Calculation of last shift end_time for daily with 10 repetitions
    final_end_time = (end_time + timedelta(weeks=12)).isoformat()
    assert response.status_code == 201
    body = response.json()
    if body:
        print(f"DEBUG: test_create_shift_recurring_daily_repeat end_time={body['end_time']}"
              f" computed={final_end_time}")
    assert body["end_time"] == final_end_time

    # List of created shifts
    get_response = client.get(f"/shifts?worker_id={worker_id}")
    assert get_response.status_code == 200

    data = get_response.json()
    assert len(data) == 4  # Initial shift plus 3 months added

def test_create_shift_recurring_daily_end_date(client: TestClient, worker_id: int):
    now = datetime.now(UTC)
    start_time = (now + timedelta(days=2, hours=1))
    end_time = (now + timedelta(days=2, hours=7))
    end_date = (now + timedelta(days=72, hours=1))

    # List of initial shifts
    get_response = client.get(f"/shifts?worker_id={worker_id}")
    assert get_response.status_code == 200

    data = get_response.json()
    assert len(data) == 0  # Empty shifts

    response = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "period": "1 day",
            "end_date": end_date.isoformat()
        },
    )

    # Calculation of last shift end_time for daily with 70 repetitions
    final_end_time = (end_time + timedelta(days=70)).isoformat()
    assert response.status_code == 201
    body = response.json()
    if body:
        print(f"DEBUG: test_create_shift_recurring_daily_repeat end_time={body['end_time']}"
              f" computed={final_end_time}")
    assert body["end_time"] == final_end_time

    # List of created shifts
    get_response = client.get(f"/shifts?worker_id={worker_id}")
    assert get_response.status_code == 200

    data = get_response.json()
    assert len(data) == 71  # Initial shift plus seventy added

def test_create_shift_recurring_weekly_end_date_less_than_start(client: TestClient, worker_id: int):
    now = datetime.now(UTC)
    start_time = (now + timedelta(days=2, hours=1))
    end_time = (now + timedelta(days=2, hours=7))
    end_date = (now + timedelta(days=2))

    # List of initial shifts
    get_response = client.get(f"/shifts?worker_id={worker_id}")
    assert get_response.status_code == 200

    data = get_response.json()
    assert len(data) == 0  # Empty shifts

    response = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "period": "weekly",
            "end_date": end_date.isoformat()
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (f"Cannot schedule recurrent shift with limiting"
                                         f" end date = {end_date.isoformat()} inferior than"
                                         f" start time = {start_time.isoformat()}.")
