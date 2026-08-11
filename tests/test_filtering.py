from fastapi.testclient import TestClient


def _create_shift(client: TestClient, worker_id: int, start: str, end: str):
    response = client.post(
        "/shifts",
        json={"worker_id": worker_id, "start_time": start, "end_time": end},
    )
    assert response.status_code == 201
    return response.json()


def test_filter_by_worker_id(client: TestClient):
    alice = client.post("/workers", json={"name": "Alice", "role": "Barista"}).json()
    bilal = client.post("/workers", json={"name": "Bilal", "role": "Cashier"}).json()

    _create_shift(client, alice["id"], "2026-08-10T09:00:00", "2026-08-10T17:00:00")
    _create_shift(client, bilal["id"], "2026-08-10T09:00:00", "2026-08-10T17:00:00")

    response = client.get("/shifts", params={"worker_id": alice["id"]})
    assert response.status_code == 200
    shifts = response.json()
    assert len(shifts) == 1
    assert shifts[0]["worker_id"] == alice["id"]


def test_filter_by_date_range(client: TestClient, worker_id: int):
    _create_shift(client, worker_id, "2026-08-10T09:00:00", "2026-08-10T17:00:00")
    _create_shift(client, worker_id, "2026-08-20T09:00:00", "2026-08-20T17:00:00")

    response = client.get(
        "/shifts",
        params={
            "start_after": "2026-08-15T00:00:00",
            "end_before": "2026-08-25T00:00:00",
        },
    )
    assert response.status_code == 200
    shifts = response.json()
    assert len(shifts) == 1
    assert shifts[0]["start_time"].startswith("2026-08-20")


def test_list_shifts_ordered_by_start_time(client: TestClient, worker_id: int):
    _create_shift(client, worker_id, "2026-08-20T09:00:00", "2026-08-20T17:00:00")
    _create_shift(client, worker_id, "2026-08-10T09:00:00", "2026-08-10T17:00:00")

    response = client.get("/shifts")
    shifts = response.json()
    starts = [s["start_time"] for s in shifts]
    assert starts == sorted(starts)


def test_list_shifts_can_sort_by_end_time_desc(client: TestClient, worker_id: int):
    _create_shift(client, worker_id, "2026-08-10T09:00:00", "2026-08-10T12:00:00")
    _create_shift(client, worker_id, "2026-08-11T09:00:00", "2026-08-11T18:00:00")

    response = client.get("/shifts", params={"sort_by": "end_time", "order": "desc"})
    assert response.status_code == 200

    shifts = response.json()
    ends = [s["end_time"] for s in shifts]
    assert ends == sorted(ends, reverse=True)


def test_list_shifts_rejects_invalid_sort_by(client: TestClient):
    response = client.get("/shifts", params={"sort_by": "worker_id"})
    assert response.status_code == 422

    detail = response.json()["detail"]
    assert detail[0]["loc"] == ["query", "sort_by"]
    assert "start_time" in detail[0]["msg"]
    assert "end_time" in detail[0]["msg"]
    assert "created_at" in detail[0]["msg"]


def test_list_shifts_rejects_invalid_order(client: TestClient):
    response = client.get("/shifts", params={"order": "up"})
    assert response.status_code == 422

    detail = response.json()["detail"]
    assert detail[0]["loc"] == ["query", "order"]
    assert "asc" in detail[0]["msg"]
    assert "desc" in detail[0]["msg"]
