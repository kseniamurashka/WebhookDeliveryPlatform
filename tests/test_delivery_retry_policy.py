import asyncio
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest
from celery.exceptions import Retry

import app.workers.tasks as tasks
from app.models.delivery import DeliveryStatus
from app.workers.tasks import DeliveryResult


def invoke_retrying_task(
    monkeypatch,
    retries: int,
    jitter: int,
) -> int:
    process_mock = AsyncMock(return_value=DeliveryResult.RETRY)
    schedule_mock = AsyncMock()
    retry_mock = Mock(side_effect=Retry())

    monkeypatch.setattr(
        tasks,
        "process_delivery",
        process_mock,
    )
    monkeypatch.setattr(
        tasks,
        "schedule_retry",
        schedule_mock,
    )
    monkeypatch.setattr(
        tasks.random,
        "randint",
        lambda minimum, maximum: jitter,
    )
    monkeypatch.setattr(
        tasks.deliver_webhook,
        "retry",
        retry_mock,
    )

    tasks.deliver_webhook.push_request(retries=retries)

    try:
        with pytest.raises(Retry):
            tasks.deliver_webhook.run(str(uuid4()))
    finally:
        tasks.deliver_webhook.pop_request()

    delay = schedule_mock.await_args.args[1]

    retry_mock.assert_called_once_with(countdown=delay)

    return delay


def test_second_retry_has_larger_backoff(monkeypatch):
    first_delay = invoke_retrying_task(
        monkeypatch,
        retries=0,
        jitter=0,
    )

    second_delay = invoke_retrying_task(
        monkeypatch,
        retries=1,
        jitter=0,
    )

    assert first_delay == 10
    assert second_delay == 20
    assert second_delay > first_delay


@pytest.mark.parametrize("jitter", [0, 1, 3, 5])
def test_retry_jitter_is_added_to_base_delay(
    monkeypatch,
    jitter,
):
    delay = invoke_retrying_task(
        monkeypatch,
        retries=1,
        jitter=jitter,
    )

    assert 20 <= delay <= 25
    assert delay == 20 + jitter


def test_max_retries_marks_delivery_dead(
    monkeypatch,
):
    delivery_id = uuid4()

    monkeypatch.setattr(
        tasks,
        "process_delivery",
        AsyncMock(return_value=DeliveryResult.RETRY),
    )

    schedule_mock = AsyncMock()
    mark_dead_mock = AsyncMock()
    retry_mock = Mock()

    monkeypatch.setattr(
        tasks,
        "schedule_retry",
        schedule_mock,
    )
    monkeypatch.setattr(
        tasks,
        "mark_delivery_dead",
        mark_dead_mock,
    )
    monkeypatch.setattr(
        tasks.deliver_webhook,
        "retry",
        retry_mock,
    )

    tasks.deliver_webhook.push_request(retries=tasks.deliver_webhook.max_retries)

    try:
        tasks.deliver_webhook.run(str(delivery_id))
    finally:
        tasks.deliver_webhook.pop_request()

    mark_dead_mock.assert_awaited_once_with(delivery_id)
    schedule_mock.assert_not_awaited()
    retry_mock.assert_not_called()


def test_mark_delivery_dead_clears_next_attempt_at(
    client,
    project_factory,
    endpoint_factory,
    subscription_factory,
    event_factory,
    delivery_factory,
    monkeypatch,
):
    delivery_id = delivery_factory()

    asyncio.run(tasks.schedule_retry(UUID(delivery_id), delay=20))
    asyncio.run(tasks.mark_delivery_dead(UUID(delivery_id)))

    delivery = client.get(f"/deliveries/{delivery_id}").json()

    assert delivery["status"] == DeliveryStatus.DEAD.value
    assert delivery["next_attempt_at"] is None


def test_dead_delivery_can_be_requeued(
    client,
    delivery_factory,
    monkeypatch,
):
    delivery_id = delivery_factory()
    asyncio.run(tasks.mark_delivery_dead(UUID(delivery_id)))
    delay_mock = Mock()
    monkeypatch.setattr(tasks.deliver_webhook, "delay", delay_mock)

    response = client.post(f"/deliveries/{delivery_id}/retry")

    assert response.status_code == 202
    assert response.json()["status"] == DeliveryStatus.PENDING.value
    delay_mock.assert_called_once_with(delivery_id)
