import pytest
from fastapi.testclient import TestClient


def test_create_worker(client: TestClient, auth_headers: dict[str, str]):
    response = client.post(
        "/workers",
        json={"name": "Jamie Lee", "role": "Cook"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Jamie Lee"
    assert body["role"] == "Cook"
    assert "id" in body


def test_update_worker(client: TestClient, auth_headers: dict[str, str]):
    create_res = client.post(
        "/workers",
        json={"name": "Jamie Lee", "role": "Cook"},
        headers=auth_headers,
    )
    worker_id = create_res.json()["id"]

    update_res = client.put(
        f"/workers/{worker_id}",
        json={"name": "Jamie Lee", "role": "Head Chef"},
        headers=auth_headers,
    )
    assert update_res.status_code == 200

    body = update_res.json()
    assert body["id"] == worker_id
    assert body["role"] == "Head Chef"


def test_update_worker_not_found(client: TestClient, auth_headers: dict[str, str]):
    response = client.put(
        "/workers/9999",
        json={"name": "Nobody", "role": "Ghost"},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_create_worker_requires_name(client: TestClient, auth_headers: dict[str, str]):
    response = client.post(
        "/workers",
        json={"name": "", "role": "Cook"},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_create_worker_sanitizes_name(client: TestClient, auth_headers: dict[str, str]):
    response = client.post(
        "/workers",
        json={"name": "Alice   Rivera", "role": "Cook"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Alice Rivera"


def test_list_workers(client: TestClient, auth_headers: dict[str, str]):
    client.post("/workers", json={"name": "Jamie Lee", "role": "Cook"}, headers=auth_headers)
    client.post("/workers", json={"name": "Sam Osei", "role": "Cashier"}, headers=auth_headers)

    response = client.get("/workers")
    assert response.status_code == 200
    names = {w["name"] for w in response.json()}
    assert names == {"Jamie Lee", "Sam Osei"}


def test_get_worker_not_found(client: TestClient):
    response = client.get("/workers/999")
    assert response.status_code == 404


def test_get_worker_with_matching_role(client: TestClient, auth_headers: dict[str, str]):
    client.post("/workers", json={"name": "Jamie Lee", "role": "Cook"}, headers=auth_headers)
    client.post("/workers", json={"name": "Sam Osei", "role": "Cashier"}, headers=auth_headers)

    response = client.get("/workers?role=Cashier")
    assert response.status_code == 200
    names = {w["name"] for w in response.json()}
    assert names == {"Sam Osei"}


def test_get_worker_with_no_matching_role(client: TestClient, auth_headers: dict[str, str]):
    client.post("/workers", json={"name": "Jamie Lee", "role": "Cook"}, headers=auth_headers)
    client.post("/workers", json={"name": "Sam Osei", "role": "Cashier"}, headers=auth_headers)

    response = client.get("/workers?role=Owner")
    assert response.status_code == 200
    names = {w["name"] for w in response.json()}
    assert names == set()


# using a parameterized function to test several case-insensitive inputs, including just firstname
@pytest.mark.parametrize(
    "search_query,expected",
    [("jamie", {"Jamie Lee"}), ("Jamie", {"Jamie Lee"}), ("Jamie Lee", {"Jamie Lee"})],
)
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


def test_worker_summary_zero_shifts(client: TestClient, auth_headers: dict[str, str]):
    create_res = client.post(
        "/workers",
        json={"name": "Jamie Lee", "role": "Cook"},
        headers=auth_headers,
    )
    assert create_res.status_code == 201
    worker_id = create_res.json()["id"]

    response = client.get(f"/workers/{worker_id}/summary")
    assert response.status_code == 200
    assert response.json()["shift_count"] == 0
    assert response.json()["total_hours"] == 0


def test_worker_summary_within_range(client: TestClient, auth_headers: dict[str, str]):
    create_res = client.post(
        "/workers",
        json={"name": "Matanat Khalil", "role": "Creator"},
        headers=auth_headers,
    )
    assert create_res.status_code == 201
    worker_id = create_res.json()["id"]

    response_within = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-10T09:00:00",
            "end_time": "2026-08-10T17:00:00",
        },
        headers=auth_headers,
    )
    assert response_within.status_code == 201

    response_out = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-09-10T09:00:00",
            "end_time": "2026-09-10T17:00:00",
        },
        headers=auth_headers,
    )
    assert response_out.status_code == 201

    response_summary_within = client.get(
        f"/workers/{worker_id}/summary?start=2026-08-01T00:00:00&end=2026-08-31T00:00:00"
    )
    assert response_summary_within.status_code == 200
    assert response_summary_within.json()["shift_count"] == 1
    assert response_summary_within.json()["total_hours"] == 8.0

    response_summary_out = client.get(
        f"/workers/{worker_id}/summary?start=2026-09-09T09:00:00&end=2026-09-09T17:00:00"
    )
    assert response_summary_out.status_code == 200
    assert response_summary_out.json()["shift_count"] == 0
    assert response_summary_out.json()["total_hours"] == 0


def test_worker_delete(client: TestClient, auth_headers: dict[str, str]):
    post_worker_response = client.post(
        "/workers",
        json={"name": "Jamie Lee", "role": "Cook"},
        headers=auth_headers,
    )
    assert post_worker_response.status_code == 201
    worker_body = post_worker_response.json()
    worker_id = worker_body["id"]

    post_shift_response = client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": "2026-08-10T09:00:00",
            "end_time": "2026-08-10T17:00:00",
        },
        headers=auth_headers,
    )
    assert post_shift_response.status_code == 201
    shift_id = post_shift_response.json()["id"]

    delete_worker_response = client.delete(f"/workers/{worker_id}", headers=auth_headers)
    assert delete_worker_response.status_code == 204

    get_worker_response = client.get(f"/workers/{worker_id}")
    assert get_worker_response.status_code == 404

    get_shift_response = client.get(f"/shifts/{shift_id}")
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
    