from collections.abc import Callable
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import Worker

PayloadFactory = Callable[[int, int], dict[str, object]]


@dataclass(frozen=True)
class RateLimitedEndpoint:
    method: str
    path: str
    payload_factory: PayloadFactory
    allowed_requests: int
    success_status_code: int


def worker_payload(_: int, request_number: int) -> dict[str, object]:
    return {"name": f"Worker {request_number}", "role": "Cook"}


def shift_payload(worker_id: int, request_number: int) -> dict[str, object]:
    day = request_number + 1
    return {
        "worker_id": worker_id,
        "start_time": f"2026-09-{day:02d}T09:00:00",
        "end_time": f"2026-09-{day:02d}T17:00:00",
    }


RATE_LIMITED_ENDPOINTS = [
    pytest.param(
        RateLimitedEndpoint(
            method="POST",
            path="/workers",
            payload_factory=worker_payload,
            allowed_requests=10,
            success_status_code=201,
        ),
        id="create-worker",
    ),
    pytest.param(
        RateLimitedEndpoint(
            method="POST",
            path="/shifts",
            payload_factory=shift_payload,
            allowed_requests=10,
            success_status_code=201,
        ),
        id="create-shift",
    ),
]


@pytest.mark.parametrize("endpoint", RATE_LIMITED_ENDPOINTS)
def test_rate_limited_endpoint_rejects_requests_over_limit(
    client: TestClient,
    session: Session,
    endpoint: RateLimitedEndpoint,
):
    worker = Worker(name="Rate Limit Worker", role="Cook")
    session.add(worker)
    session.commit()
    session.refresh(worker)
    assert worker.id is not None

    for request_number in range(endpoint.allowed_requests):
        response = client.request(
            endpoint.method,
            endpoint.path,
            json=endpoint.payload_factory(worker.id, request_number),
        )
        assert response.status_code == endpoint.success_status_code

    response = client.request(
        endpoint.method,
        endpoint.path,
        json=endpoint.payload_factory(worker.id, endpoint.allowed_requests),
    )

    assert response.status_code == 429
    assert "Rate limit exceeded" in response.json()["error"]


def test_unlimited_endpoint_is_not_rate_limited(client: TestClient):
    for _ in range(20):
        response = client.get("/")
        assert response.status_code == 200
