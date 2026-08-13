from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlmodel import Session

from app.models import Shift, Worker

RequestFactory = Callable[[TestClient, Session, int, int], Response]


@dataclass(frozen=True)
class RateLimitedEndpoint:
    request_factory: RequestFactory
    allowed_requests: int
    success_status_code: int


def create_worker_request(
    client: TestClient,
    _: Session,
    __: int,
    request_number: int,
) -> Response:
    return client.post(
        "/workers",
        json={"name": f"Worker {request_number}", "role": "Cook"},
    )


def create_shift_request(
    client: TestClient,
    _: Session,
    worker_id: int,
    request_number: int,
) -> Response:
    day = request_number + 1
    return client.post(
        "/shifts",
        json={
            "worker_id": worker_id,
            "start_time": f"2026-09-{day:02d}T09:00:00",
            "end_time": f"2026-09-{day:02d}T17:00:00",
        },
    )


def update_worker_request(
    client: TestClient,
    _: Session,
    worker_id: int,
    request_number: int,
) -> Response:
    return client.put(
        f"/workers/{worker_id}",
        json={"name": f"Updated Worker {request_number}", "role": "Cook"},
    )


def delete_shift_request(
    client: TestClient,
    session: Session,
    worker_id: int,
    request_number: int,
) -> Response:
    day = request_number + 1
    shift = Shift(
        worker_id=worker_id,
        start_time=datetime(2026, 10, day, 9, tzinfo=UTC),
        end_time=datetime(2026, 10, day, 17, tzinfo=UTC),
    )
    session.add(shift)
    session.commit()
    session.refresh(shift)
    assert shift.id is not None

    return client.delete(f"/shifts/{shift.id}")


RATE_LIMITED_ENDPOINTS = [
    pytest.param(
        RateLimitedEndpoint(
            request_factory=create_worker_request,
            allowed_requests=10,
            success_status_code=201,
        ),
        id="create-worker",
    ),
    pytest.param(
        RateLimitedEndpoint(
            request_factory=create_shift_request,
            allowed_requests=10,
            success_status_code=201,
        ),
        id="create-shift",
    ),
    pytest.param(
        RateLimitedEndpoint(
            request_factory=update_worker_request,
            allowed_requests=10,
            success_status_code=200,
        ),
        id="update-worker",
    ),
    pytest.param(
        RateLimitedEndpoint(
            request_factory=delete_shift_request,
            allowed_requests=10,
            success_status_code=204,
        ),
        id="delete-shift",
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
        response = endpoint.request_factory(
            client,
            session,
            worker.id,
            request_number,
        )
        assert response.status_code == endpoint.success_status_code

    response = endpoint.request_factory(
        client,
        session,
        worker.id,
        endpoint.allowed_requests,
    )

    assert response.status_code == 429
    assert "Rate limit exceeded" in response.json()["error"]


def test_unlimited_endpoint_is_not_rate_limited(client: TestClient):
    for _ in range(20):
        response = client.get("/")
        assert response.status_code == 200
