from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_api_key
from app.db.dependencies import get_db
from app.models.delivery import Delivery, DeliveryStatus
from app.models.delivery_attempt import DeliveryAttempt
from app.schemas.delivery import DeliveryResponse
from app.schemas.delivery_attempts import DeliveryAttemptResponse
from app.workers.tasks import deliver_webhook

router = APIRouter(
    prefix="/deliveries",
    tags=["Deliveries"],
    dependencies=[Depends(require_api_key)],
)


@router.get("", response_model=list[DeliveryResponse])
async def get_deliveries(
    db: Annotated[AsyncSession, Depends(get_db)],
    status: DeliveryStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    stmt = select(Delivery)

    if status is not None:
        stmt = stmt.where(Delivery.status == status)

    stmt = stmt.order_by(Delivery.created_at.desc()).limit(limit).offset(offset)

    result = await db.execute(stmt)

    return result.scalars().all()


@router.get("/{delivery_id}", response_model=DeliveryResponse)
async def get_delivery(delivery_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    delivery = await db.get(Delivery, delivery_id)

    if delivery is None:
        raise HTTPException(
            status_code=404,
            detail="Delivery not found",
        )

    return delivery


@router.post(
    "/{delivery_id}/retry",
    response_model=DeliveryResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_delivery(
    delivery_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    delivery = await db.get(Delivery, delivery_id)
    if delivery is None:
        raise HTTPException(status_code=404, detail="Delivery not found")
    if delivery.status is not DeliveryStatus.DEAD:
        raise HTTPException(
            status_code=409,
            detail="Only dead deliveries can be retried manually",
        )

    delivery.status = DeliveryStatus.PENDING
    delivery.next_attempt_at = None
    await db.commit()
    await db.refresh(delivery)
    deliver_webhook.delay(str(delivery.id))
    return delivery


@router.get("/{delivery_id}/attempts", response_model=list[DeliveryAttemptResponse])
async def get_delivery_attempts(delivery_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    delivery = await db.get(Delivery, delivery_id)

    if delivery is None:
        raise HTTPException(
            status_code=404,
            detail="Delivery not found",
        )

    stmt = (
        select(DeliveryAttempt)
        .where(DeliveryAttempt.delivery_id == delivery.id)
        .order_by(DeliveryAttempt.started_at.asc())
    )

    result = await db.execute(stmt)
    attempts = result.scalars().all()
    return attempts
