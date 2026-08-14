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

def test_worker_summary_unknown_worker(client: TestClient):
    response = client.get("/workers/9999/summary")
    assert response.status_code == 404

def test_worker_summary_zero_shifts(client: TestClient):
    '''
    Create a new worker and immediately call the summary endpoint
    since a fresh worker has no shifts
    '''
    create_res = client.post("/workers", json={"name": "Jamie Lee", "role": "Cook"})
    assert create_res.status_code == 201
    worker_id = create_res.json()["id"]

    response = client.get(f"/workers/{worker_id}/summary")
    assert response.status_code == 200

    assert response.json()["shift_count"]==0
    assert response.json()["total_hours"]==0


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
    response_summary_within = client.get(f"/workers/{worker_id}/summary?start=2026-08-01T00:00:00&end=2026-08-31T00:00:00")
    assert response_summary_within.status_code == 200

    assert response_summary_within.json()["shift_count"]==1
    assert response_summary_within.json()["total_hours"]==8 # between 17:00 and 9:00

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

