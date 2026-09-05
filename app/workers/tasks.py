import asyncio
import json
import logging
import random
from datetime import UTC, datetime, timedelta
from enum import Enum
from time import perf_counter
from uuid import UUID

from celery import Task
from httpx import AsyncClient, RequestError
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.core.config import settings
from app.db.worker_session import worker_session_factory
from app.models.delivery import Delivery, DeliveryStatus
from app.models.delivery_attempt import DeliveryAttempt
from app.services.signature import generate_signature
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


class DeliveryResult(Enum):
    SUCCESS = "SUCCESS"
    RETRY = "RETRY"
    SKIP = "SKIP"
    DEAD = "DEAD"


def is_retryable_status(status_code: int) -> bool:
    """
    408 - Request Timeout
    429 - Too Many Requests — retry нужен
    5xx - проблема на стороне получателя
    """
    return status_code in {408, 429} or 500 <= status_code < 600


async def process_delivery(delivery_id: UUID) -> DeliveryResult:
    async with worker_session_factory() as db:
        stmt = (
            select(Delivery)
            .options(
                joinedload(Delivery.event),
                joinedload(Delivery.endpoint),
            )
            .where(Delivery.id == delivery_id)
            .with_for_update(of=Delivery)
        )

        result = await db.execute(stmt)

        delivery = result.scalar_one_or_none()
        if delivery is None:
            logger.warning("Delivery not found: %s", delivery_id)
            return DeliveryResult.SKIP

        if delivery.status not in {DeliveryStatus.PENDING, DeliveryStatus.RETRYING}:
            logger.info(
                "Skipping delivery %s with status %s",
                delivery_id,
                delivery.status.value,
            )
            return DeliveryResult.SKIP

        if not delivery.endpoint.is_active:
            delivery.status = DeliveryStatus.DEAD
            delivery.next_attempt_at = None
            await db.commit()
            logger.info("Endpoint is inactive; delivery %s marked dead", delivery_id)
            return DeliveryResult.DEAD

        delivery.status = DeliveryStatus.PROCESSING
        await db.commit()

        payload = {
            "id": str(delivery.event.id),
            "type": delivery.event.event_type,
            "created_at": delivery.event.created_at.isoformat(),
            "data": delivery.event.payload,
        }

        started_at = datetime.now(UTC)
        started = perf_counter()

        try:
            async with AsyncClient() as client:
                body = json.dumps(
                    payload,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("utf-8")

                timestamp = str(int(started_at.timestamp()))

                signature = generate_signature(delivery.endpoint.secret, timestamp, body)

                headers = {
                    "Content-Type": "application/json",
                    "X-Webhook-Id": str(delivery.event.id),
                    "X-Webhook-Delivery": str(delivery.id),
                    "X-Webhook-Timestamp": timestamp,
                    "X-Webhook-Signature": signature,
                    "User-Agent": "WebhookDeliveryPlatform/1.0",
                }

                response = await client.post(
                    delivery.endpoint.url,
                    content=body,
                    headers=headers,
                    timeout=settings.delivery_timeout_seconds,
                )

            duration_ms = int((perf_counter() - started) * 1000)

            attempt = DeliveryAttempt(
                delivery_id=delivery.id,
                status_code=response.status_code,
                response_body=response.text[: settings.max_response_body_length],
                error=None,
                duration_ms=duration_ms,
                started_at=started_at,
                finished_at=datetime.now(UTC),
            )

            delivery.attempt_count += 1

            if response.is_success:
                delivery.status = DeliveryStatus.SUCCESS
                delivery.next_attempt_at = None
                result = DeliveryResult.SUCCESS
            elif is_retryable_status(response.status_code):
                delivery.status = DeliveryStatus.RETRYING
                result = DeliveryResult.RETRY
            else:
                delivery.status = DeliveryStatus.DEAD
                delivery.next_attempt_at = None
                result = DeliveryResult.DEAD

            db.add(attempt)
            await db.commit()

            logger.info(
                "Delivery %s finished with HTTP %s in %sms",
                delivery_id,
                response.status_code,
                duration_ms,
            )

            return result
        except RequestError as exc:
            duration_ms = int((perf_counter() - started) * 1000)

            attempt = DeliveryAttempt(
                delivery_id=delivery.id,
                status_code=None,
                response_body=None,
                error=str(exc),
                duration_ms=duration_ms,
                started_at=started_at,
                finished_at=datetime.now(UTC),
            )

            delivery.attempt_count += 1
            delivery.status = DeliveryStatus.RETRYING

            db.add(attempt)
            await db.commit()

            logger.warning("Delivery %s failed: %s", delivery_id, exc)

            return DeliveryResult.RETRY


async def schedule_retry(
    delivery_id: UUID,
    delay: int,
):
    async with worker_session_factory() as db:
        delivery = await db.get(Delivery, delivery_id)

        if delivery is None:
            return

        delivery.status = DeliveryStatus.RETRYING
        delivery.next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay)

        await db.commit()


async def mark_delivery_dead(delivery_id: UUID):
    async with worker_session_factory() as db:
        delivery = await db.get(Delivery, delivery_id)

        if delivery is None:
            return

        delivery.status = DeliveryStatus.DEAD
        delivery.next_attempt_at = None

        await db.commit()


@celery_app.task(
    bind=True,
    max_retries=5,
)
def deliver_webhook(self: Task, delivery_id: str):
    delivery_uuid = UUID(delivery_id)
    result = asyncio.run(process_delivery(delivery_uuid))

    if result is DeliveryResult.RETRY:
        if self.request.retries >= self.max_retries:
            asyncio.run(mark_delivery_dead(delivery_uuid))
            return

        delay = min(
            10 * (2**self.request.retries),
            3600,
        )
        jitter = random.randint(0, 5)
        delay += jitter

        asyncio.run(
            schedule_retry(
                delivery_uuid,
                delay,
            )
        )

        raise self.retry(countdown=delay)
