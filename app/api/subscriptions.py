from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_api_key
from app.db.dependencies import get_db
from app.models.endpoint import Endpoint
from app.models.subscription import Subscription
from app.schemas.subscription import SubscriptionCreate, SubscriptionResponse

router = APIRouter(
    prefix="/subscriptions",
    tags=["Subscriptions"],
    dependencies=[Depends(require_api_key)],
)


@router.get("", response_model=list[SubscriptionResponse])
async def list_subscriptions(
    db: Annotated[AsyncSession, Depends(get_db)],
    endpoint_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    stmt = select(Subscription)
    if endpoint_id is not None:
        stmt = stmt.where(Subscription.endpoint_id == endpoint_id)
    result = await db.execute(
        stmt.order_by(Subscription.created_at.desc()).limit(limit).offset(offset)
    )
    return result.scalars().all()


@router.post("", response_model=SubscriptionResponse, status_code=201)
async def create_subscription(
    data: SubscriptionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    endpoint = await db.get(Endpoint, data.endpoint_id)
    if endpoint is None:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    subscription = Subscription(
        endpoint_id=data.endpoint_id,
        event_type=data.event_type,
    )

    db.add(subscription)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Subscription already exists",
        ) from None

    await db.refresh(subscription)

    return subscription


@router.delete("/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription(
    subscription_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    subscription = await db.get(Subscription, subscription_id)
    if subscription is None:
        raise HTTPException(status_code=404, detail="Subscription not found")

    await db.delete(subscription)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
