import pytest
from fastapi.testclient import TestClient
from tests import test_shifts

def test_create_worker(client: TestClient):
    response = client.post("/workers", json={"name": "Jamie Lee", "role": "Cook"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Jamie Lee"
    assert body["role"] == "Cook"
    assert "id" in body

def test_update_worker(client: TestClient):
    create_res = client.post("/workers", json={"name": "Jamie Lee", "role": "Cook"})
    worker_id = create_res.json()["id"]

    update_res = client.put(f"/workers/{worker_id}", json={"name": "Jamie Lee", "role": "Head Chef"})
    assert update_res.status_code == 200

    body = update_res.json()
    assert body["id"] == worker_id
    assert body["role"] == "Head Chef"

def test_update_worker_not_found(client: TestClient):
    response = client.put("/workers/9999", json={"name": "Nobody", "role": "Ghost"})
    assert response.status_code == 404


def test_create_worker_requires_name(client: TestClient):
    response = client.post("/workers", json={"name": "", "role": "Cook"})
    assert response.status_code == 422


def test_create_worker_sanitizes_name(client: TestClient):
    response = client.post("/workers", json={"name": "Alice   Rivera", "role": "Cook"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Alice Rivera"


def test_list_workers(client: TestClient):
    client.post("/workers", json={"name": "Jamie Lee", "role": "Cook"})
    client.post("/workers", json={"name": "Sam Osei", "role": "Cashier"})

    response = client.get("/workers")
    assert response.status_code == 200
    names = {w["name"] for w in response.json()}
    assert names == {"Jamie Lee", "Sam Osei"}


def test_get_worker_not_found(client: TestClient):
    response = client.get("/workers/999")
    assert response.status_code == 404


def test_get_worker_with_matching_role(client: TestClient):
    client.post("/workers", json={"name": "Jamie Lee", "role": "Cook"})
    client.post("/workers", json={"name": "Sam Osei", "role": "Cashier"})

    response = client.get("/workers?role=Cashier")
    names = {w["name"] for w in response.json()}
    assert names == {"Sam Osei"}


def test_get_worker_with_no_matching_role(client: TestClient):
    client.post("/workers", json={"name": "Jamie Lee", "role": "Cook"})
    client.post("/workers", json={"name": "Sam Osei", "role": "Cashier"})

    response = client.get("/workers?role=Owner")
    names = {w["name"] for w in response.json()}
    assert names == set()

# using a parameterized function to test several case-insensitive inputs, including just firstname
@pytest.mark.parametrize("search_query,expected", [("jamie", {"Jamie Lee"}), ("Jamie", {"Jamie Lee"}), ("Jamie Lee", {"Jamie Lee"})])
def test_get_worker_with_matching_name(client: TestClient, search_query: str, expected: set):
    client.post("/workers", json={"name": "Jamie Lee", "role": "Cook"})
    client.post("/workers", json={"name": "Sam Osei", "role": "Cashier"})

    response = client.get(f"/workers?name={search_query}")
    names = {w["name"] for w in response.json()}
    assert names == expected

def test_get_worker_with_no_matching_name(client: TestClient):
    client.post("/workers", json={"name": "Jamie Lee", "role": "Cook"})
    client.post("/workers", json={"name": "Sam Osei", "role": "Cashier"})

    response = client.get("/workers?name=Carmen Diaz")
    names = {w["name"] for w in response.json()}
    assert names == set()

def test_get_worker_with_role_and_name(client: TestClient):
    client.post("/workers", json={"name": "Jamie Lee", "role": "Cook"})
    client.post("/workers", json={"name": "Sam Osei", "role": "Cashier"})

    response = client.get("/workers?role=Cashier&name=Sam Osei")
    names = {w["name"] for w in response.json()}
    assert names == {"Sam Osei"}

def test_worker_summary_unknown_worker(client: TestClient):
    response = client.get("/workers/9999/summary")
    assert response.status_code == 404


def test_worker_summary_zero_shifts(client: TestClient):
    """
    Create a new worker and immediately call the summary endpoint
    since a fresh worker has no shifts
    """
    create_res = client.post("/workers", json={"name": "Jamie Lee", "role": "Cook"})
    assert create_res.status_code == 201
    worker_id = create_res.json()["id"]

    response = client.get(f"/workers/{worker_id}/summary")
    assert response.status_code == 200

    assert response.json()["shift_count"] == 0
    assert response.json()["total_hours"] == 0


def test_worker_summary_within_range(client: TestClient):
    # Create a brand new worker:
    create_res = client.post("/workers", json={"name": "Matanat Khalil", "role": "Creator"})
    assert create_res.status_code == 201
    worker_id = create_res.json()["id"]

    # Create a shift within the range for this worker:
    response_within = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-10T09:00:00",
            "end_time": "2026-08-10T17:00:00",
        },
    )
    assert response_within.status_code == 201

    # Create a shift outside the range for this worker:
    response_out = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-09-10T09:00:00",
            "end_time": "2026-09-10T17:00:00",
        },
    )
    assert response_out.status_code == 201

    # Call the summary endpoint for both:
    response_summary_within = client.get(
        f"/workers/{worker_id}/summary?start=2026-08-01T00:00:00&end=2026-08-31T00:00:00"
    )
    assert response_summary_within.status_code == 200

    assert response_summary_within.json()["shift_count"] == 1
    assert response_summary_within.json()["total_hours"] == 8  # between 17:00 and 9:00

    response_summary_out = client.get(f"/workers/{worker_id}/summary?start=2026-09-09T09:00:00&end=2026-09-09T17:00:00")
    assert response_summary_out.status_code == 200

    assert response_summary_out.json()["shift_count"]==0
    assert response_summary_out.json()["total_hours"]==0

def test_worker_delete(client: TestClient):
    post_worker_response = client.post("/workers", json={"name": "Jamie Lee", "role":"Cook"})
    assert post_worker_response.status_code == 201
    worker_body = post_worker_response.json()
    assert worker_body["name"] == "Jamie Lee"
    assert worker_body["role"] == "Cook"
    assert "id" in worker_body
    workerId = worker_body["id"]

    post_shift_response = client.post(
        "/shifts",
        json={
            "worker_id": workerId,
            "start_time": "2026-08-10T09:00:00",
            "end_time": "2026-08-10T17:00:00",
        },
    )
    assert post_shift_response.status_code == 201
    shift_body = post_shift_response.json()
    assert shift_body["worker_id"] == workerId
    assert "id" in shift_body
    assert "created_at" in shift_body
    shiftId = shift_body["id"]

    delete_worker_response = client.delete(f"/workers/{workerId}")
    assert delete_worker_response.status_code == 204

    get_worker_response = client.get(f"/workers/{workerId}")
    assert get_worker_response.status_code == 404

    get_shift_response = client.get(f"/shifts/{shiftId}")
    assert get_shift_response.status_code == 404


def test_deactivate_worker(client: TestClient):
    worker = client.post(
        "/workers", json={"name": "Jamie Lee", "role": "Cook"}
    ).json()

    response = client.put(
        f"/workers/{worker['id']}",
        json={"name": worker["name"], "role": worker["role"], "active": False},
    )

    assert response.status_code == 200
    assert response.json()["active"] is False


def test_inactive_worker_excluded_from_default_list(client: TestClient):
    inactive_worker = client.post(
        "/workers", json={"name": "Jamie Lee", "role": "Cook"}
    ).json()
    client.put(
        f"/workers/{inactive_worker['id']}",
        json={
            "name": inactive_worker["name"],
            "role": inactive_worker["role"],
            "active": False,
        },
    )

    response = client.get("/workers")

    assert response.status_code == 200
    assert inactive_worker["id"] not in {worker["id"] for worker in response.json()}

def test_workers_summary_multiple_workers_returns_correct_summary(client: TestClient):
    # Create two workers
    worker1 = client.post("/workers", json={"name": "Worker One", "role": "Role A"}).json()
    worker2 = client.post("/workers", json={"name": "Worker Two", "role": "Role B"}).json()

    # Create shifts for both workers
    client.post(
        "/shifts",
        json={
            "worker_id": worker1["id"],
            "start_time": "2026-08-10T09:00:00",
            "end_time": "2026-08-10T17:00:00",
        },
    )
    client.post(
        "/shifts",
        json={
            "worker_id": worker2["id"],
            "start_time": "2026-08-11T10:00:00",
            "end_time": "2026-08-11T15:00:00",
        },
    )

    # Get the summary for all workers
    response = client.get("/workers/summary")
    assert response.status_code == 200

    summary = response.json()
    assert summary["grand_total_hours"] == 13.0  # 8 + 5 hours
    assert summary["total_shift_count"] == 2

    worker_summaries = {ws["worker_id"]: ws for ws in summary["workers"]}
    assert worker_summaries[worker1["id"]]["total_hours"] == 8.0
    assert worker_summaries[worker1["id"]]["shift_count"] == 1
    assert worker_summaries[worker1["id"]]["average_shift_hours"] == 8.0
    assert worker_summaries[worker2["id"]]["total_hours"] == 5.0
    assert worker_summaries[worker2["id"]]["shift_count"] == 1
    assert worker_summaries[worker2["id"]]["average_shift_hours"] == 5.0

def test_workers_summary_zero_shifts(client: TestClient):
    # Create a worker with no shifts
    worker = client.post("/workers", json={"name": "Worker Zero", "role": "Role Z"}).json()

    # Get the summary for all workers
    response = client.get("/workers/summary")
    assert response.status_code == 200

    summary = response.json()
    assert summary["grand_total_hours"] == 0.0
    assert summary["total_shift_count"] == 0

    worker_summaries = {ws["worker_id"]: ws for ws in summary["workers"]}
    assert worker_summaries[worker["id"]]["total_hours"] == 0.0
    assert worker_summaries[worker["id"]]["shift_count"] == 0
    assert worker_summaries[worker["id"]]["average_shift_hours"] == 0.0


def test_workers_summary_filters_by_date_range(client: TestClient):
    # Create a worker
    worker = client.post("/workers", json={"name": "Worker Date", "role": "Role D"}).json()

    # Create shifts for the worker, some within the date range and some outside
    client.post(
        "/shifts",
        json={
            "worker_id": worker["id"],
            "start_time": "2026-08-10T09:00:00",
            "end_time": "2026-08-10T17:00:00",
        },
    )
    client.post(
        "/shifts",
        json={
            "worker_id": worker["id"],
            "start_time": "2026-09-10T09:00:00",
            "end_time": "2026-09-10T17:00:00",
        },
    )

    # Get the summary for all workers within a specific date range
    response = client.get("/workers/summary?start=2026-08-01T00:00:00&end=2026-08-31T23:59:59")
    assert response.status_code == 200

    summary = response.json()
    assert summary["grand_total_hours"] == 8.0  # Only the August shift counts
    assert summary["total_shift_count"] == 1

    worker_summaries = {ws["worker_id"]: ws for ws in summary["workers"]}
    assert worker_summaries[worker["id"]]["total_hours"] == 8.0
    assert worker_summaries[worker["id"]]["shift_count"] == 1
    assert worker_summaries[worker["id"]]["average_shift_hours"] == 8.0


def test_workers_summary_no_date_range_includes_all_shifts(client: TestClient):
    # Create a worker
    worker = client.post("/workers", json={"name": "Worker All", "role": "Role A"}).json()

    # Create shifts for the worker
    client.post(
        "/shifts",
        json={
            "worker_id": worker["id"],
            "start_time": "2026-08-10T09:00:00",
            "end_time": "2026-08-10T17:00:00",
        },
    )
    client.post(
        "/shifts",
        json={
            "worker_id": worker["id"],
            "start_time": "2026-09-10T09:00:00",
            "end_time": "2026-09-10T17:00:00",
        },
    )

    # Get the summary for all workers without specifying a date range
    response = client.get("/workers/summary")
    assert response.status_code == 200

    summary = response.json()
    assert summary["grand_total_hours"] == 16.0  # Both shifts count
    assert summary["total_shift_count"] == 2

    worker_summaries = {ws["worker_id"]: ws for ws in summary["workers"]}
    assert worker_summaries[worker["id"]]["total_hours"] == 16.0
    assert worker_summaries[worker["id"]]["shift_count"] == 2
    assert worker_summaries[worker["id"]]["average_shift_hours"] == 8.0


def test_workers_summary_no_workers_returns_empty_list_and_zero_grand_total(client: TestClient):
    # Ensure there are no workers in the system
    response = client.get("/workers/summary")
    assert response.status_code == 200

    summary = response.json()
    assert summary["grand_total_hours"] == 0.0
    assert summary["total_shift_count"] == 0
    assert summary["workers"] == []


def test_workers_summary_grand_total_matches_sum_of_individual_totals(client: TestClient):
    # Create two workers
    worker1 = client.post("/workers", json={"name": "Worker One", "role": "Role A"}).json()
    worker2 = client.post("/workers", json={"name": "Worker Two", "role": "Role B"}).json()

    # Create shifts for both workers
    client.post(
        "/shifts",
        json={
            "worker_id": worker1["id"],
            "start_time": "2026-08-10T09:00:00",
            "end_time": "2026-08-10T17:00:00",
        },
    )
    client.post(
        "/shifts",
        json={
            "worker_id": worker2["id"],
            "start_time": "2026-08-11T10:00:00",
            "end_time": "2026-08-11T15:00:00",
        },
    )

    # Get the summary for all workers
    response = client.get("/workers/summary")
    assert response.status_code == 200

    summary = response.json()
    total_hours_from_workers = sum(ws["total_hours"] for ws in summary["workers"])
    assert summary["grand_total_hours"] == total_hours_from_workers


def test_workers_summary_total_shift_count_matches_sum_of_individual_counts(client: TestClient):
    # Create two workers
    worker1 = client.post("/workers", json={"name": "Worker One", "role": "Role A"}).json()
    worker2 = client.post("/workers", json={"name": "Worker Two", "role": "Role B"}).json()

    # Create shifts for both workers
    client.post(
        "/shifts",
        json={
            "worker_id": worker1["id"],
            "start_time": "2026-08-10T09:00:00",
            "end_time": "2026-08-10T17:00:00",
        },
    )
    client.post(
        "/shifts",
        json={
            "worker_id": worker2["id"],
            "start_time": "2026-08-11T10:00:00",
            "end_time": "2026-08-11T15:00:00",
        },
    )

    # Get the summary for all workers
    response = client.get("/workers/summary")
    assert response.status_code == 200

    summary = response.json()
    total_shift_count_from_workers = sum(ws["shift_count"] for ws in summary["workers"])
    assert summary["total_shift_count"] == total_shift_count_from_workers

def test_workers_summary_average_shift_hours(client: TestClient):
    # create two workers
    worker1 = client.post("/workers", json={"name": "Worker Average 1", "role": "Role A"}).json()
    worker2 = client.post("/workers", json={"name": "Worker Average 2", "role": "Role B"}).json()

    # create shifts for the workers
    client.post(
            "/shifts",
            json={
                "worker_id": worker1["id"],
                "start_time": "2026-08-10T09:00:00",
                "end_time": "2026-08-10T17:00:00",
            },
        )
    
    client.post(
        "/shifts",
        json={
            "worker_id": worker1["id"],
            "start_time": "2026-08-11T10:00:00",
            "end_time": "2026-08-11T15:00:00",
        },
    )

    client.post(
            "/shifts",
            json={
                "worker_id": worker2["id"],
                "start_time": "2026-09-10T09:00:00",
                "end_time": "2026-09-10T17:00:00",
            },
    )

    client.post(
            "/shifts",
            json={
                "worker_id": worker2["id"],
                "start_time": "2026-09-12T12:00:00",
                "end_time": "2026-09-12T18:00:00",
            },
    )

    # Get the summary for all workers
    response = client.get("/workers/summary")
    assert response.status_code == 200

    summary = response.json()
    assert summary["grand_total_hours"] == 27.0
    assert summary["total_shift_count"] == 4

    worker_summaries = {ws["worker_id"]: ws for ws in summary["workers"]}
    assert worker_summaries[worker1["id"]]["total_hours"] == 13.0 # 8 + 5
    assert worker_summaries[worker1["id"]]["shift_count"] == 2
    assert worker_summaries[worker1["id"]]["average_shift_hours"] == 6.5
    assert worker_summaries[worker2["id"]]["total_hours"] == 14.0 # 8 + 6
    assert worker_summaries[worker2["id"]]["shift_count"] == 2
    assert worker_summaries[worker2["id"]]["average_shift_hours"] == 7.0
