from fastapi.testclient import TestClient


def test_create_worker(client: TestClient):
    response = client.post("/workers", json={"name": "Jamie Lee", "role": "Cook"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Jamie Lee"
    assert body["role"] == "Cook"
    assert "id" in body


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
