import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest

from app.models.delivery import DeliveryStatus
from app.workers.tasks import DeliveryResult, process_delivery, schedule_retry


def test_successful_delivery(
    client,
    project_factory,
    endpoint_factory,
    subscription_factory,
    event_factory,
    delivery_factory,
    monkeypatch,
):
    delivery_id = delivery_factory()

    mock_response = httpx.Response(
        status_code=200,
        text="OK",
    )
    monkeypatch.setattr(
        "app.workers.tasks.AsyncClient.post",
        AsyncMock(return_value=mock_response),
    )

    result = asyncio.run(process_delivery(UUID(delivery_id)))
    assert result is DeliveryResult.SUCCESS

    response = client.get(f"/deliveries/{delivery_id}")
    assert response.status_code == 200

    delivery = response.json()
    assert delivery["status"] == DeliveryStatus.SUCCESS.value
    assert delivery["next_attempt_at"] is None
    assert delivery["attempt_count"] == 1

    attempts = client.get(f"/deliveries/{delivery_id}/attempts").json()
    assert len(attempts) == 1
    assert attempts[0]["status_code"] == 200
    assert attempts[0]["error"] is None


def test_failed_http_response_marks_delivery_for_retry(
    client,
    project_factory,
    endpoint_factory,
    subscription_factory,
    event_factory,
    delivery_factory,
    monkeypatch,
):
    delivery_id = delivery_factory()

    mock_response = httpx.Response(
        status_code=500,
        text="Internal Server Error",
    )
    monkeypatch.setattr(
        "app.workers.tasks.AsyncClient.post",
        AsyncMock(return_value=mock_response),
    )

    result = asyncio.run(process_delivery(UUID(delivery_id)))
    assert result is DeliveryResult.RETRY

    delivery = client.get(f"/deliveries/{delivery_id}").json()
    assert delivery["status"] == DeliveryStatus.RETRYING.value
    assert delivery["next_attempt_at"] is None
    assert delivery["attempt_count"] == 1

    before = datetime.now(UTC)

    asyncio.run(
        schedule_retry(
            UUID(delivery_id),
            delay=20,
        )
    )

    after = datetime.now(UTC)

    delivery = client.get(f"/deliveries/{delivery_id}").json()
    next_attempt_at = datetime.fromisoformat(delivery["next_attempt_at"])

    assert before + timedelta(seconds=20) <= next_attempt_at
    assert next_attempt_at <= after + timedelta(seconds=20)

    attempts = client.get(f"/deliveries/{delivery_id}/attempts").json()
    assert len(attempts) == 1

    attempt = attempts[0]
    assert attempt["status_code"] == 500
    assert attempt["error"] is None
    assert attempt["response_body"] == "Internal Server Error"


@pytest.mark.parametrize(
    "exception_class",
    [
        httpx.ConnectError,
        httpx.ReadTimeout,
    ],
)
def test_network_error_marks_delivery_for_retry(
    client,
    project_factory,
    endpoint_factory,
    subscription_factory,
    event_factory,
    monkeypatch,
    delivery_factory,
    exception_class,
):
    delivery_id = delivery_factory()

    request = httpx.Request(
        "POST",
        "https://example.com/webhook",
    )

    error = exception_class(
        "Connection refused",
        request=request,
    )

    monkeypatch.setattr(
        "app.workers.tasks.AsyncClient.post",
        AsyncMock(side_effect=error),
    )

    result = asyncio.run(process_delivery(UUID(delivery_id)))
    assert result is DeliveryResult.RETRY

    delivery = client.get(f"/deliveries/{delivery_id}").json()
    assert delivery["status"] == DeliveryStatus.RETRYING.value
    assert delivery["attempt_count"] == 1

    attempts = client.get(f"/deliveries/{delivery_id}/attempts").json()
    assert len(attempts) == 1

    attempt = attempts[0]
    assert attempt["status_code"] is None
    assert "Connection refused" in attempt["error"]
    assert attempt["response_body"] is None


def test_missing_delivery_is_skipped():
    delivery_id = uuid4()

    result = asyncio.run(process_delivery(delivery_id))

    assert result is DeliveryResult.SKIP


def test_two_attempts_after_failure(
    client,
    project_factory,
    endpoint_factory,
    subscription_factory,
    event_factory,
    delivery_factory,
    monkeypatch,
):
    delivery_id = delivery_factory()

    mock_fail_response = httpx.Response(
        status_code=500,
        text="Internal Server Error",
    )
    monkeypatch.setattr(
        "app.workers.tasks.AsyncClient.post",
        AsyncMock(return_value=mock_fail_response),
    )

    result = asyncio.run(process_delivery(UUID(delivery_id)))
    assert result is DeliveryResult.RETRY

    asyncio.run(
        schedule_retry(
            UUID(delivery_id),
            delay=20,
        )
    )

    delivery = client.get(f"/deliveries/{delivery_id}").json()
    assert delivery["status"] == DeliveryStatus.RETRYING.value
    assert delivery["next_attempt_at"] is not None
    assert delivery["attempt_count"] == 1

    mock_success_response = httpx.Response(
        status_code=200,
        text="OK",
    )
    monkeypatch.setattr(
        "app.workers.tasks.AsyncClient.post",
        AsyncMock(return_value=mock_success_response),
    )

    result = asyncio.run(process_delivery(UUID(delivery_id)))
    assert result is DeliveryResult.SUCCESS
    delivery = client.get(f"/deliveries/{delivery_id}").json()
    assert delivery["status"] == DeliveryStatus.SUCCESS.value
    assert delivery["next_attempt_at"] is None
    assert delivery["attempt_count"] == 2

    attempts = client.get(f"/deliveries/{delivery_id}/attempts").json()
    assert len(attempts) == 2

    assert attempts[0]["status_code"] == 500
    assert attempts[0]["response_body"] == "Internal Server Error"
    assert attempts[0]["error"] is None

    assert attempts[1]["status_code"] == 200
    assert attempts[1]["response_body"] == "OK"
    assert attempts[1]["error"] is None


def test_successful_delivery_is_not_sent_twice(
    client,
    delivery_factory,
    monkeypatch,
):
    delivery_id = delivery_factory()
    post_mock = AsyncMock(return_value=httpx.Response(status_code=200, text="OK"))
    monkeypatch.setattr("app.workers.tasks.AsyncClient.post", post_mock)

    first_result = asyncio.run(process_delivery(UUID(delivery_id)))
    second_result = asyncio.run(process_delivery(UUID(delivery_id)))

    assert first_result is DeliveryResult.SUCCESS
    assert second_result is DeliveryResult.SKIP
    assert post_mock.await_count == 1
