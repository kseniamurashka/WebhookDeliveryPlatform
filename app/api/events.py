from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_api_key
from app.db.dependencies import get_db
from app.models.delivery import Delivery
from app.models.endpoint import Endpoint
from app.models.event import Event
from app.models.project import Project
from app.models.subscription import Subscription
from app.schemas.delivery import DeliveryResponse
from app.schemas.event import EventCreate, EventResponse
from app.workers.tasks import deliver_webhook

router = APIRouter(
    prefix="/events",
    tags=["Events"],
    dependencies=[Depends(require_api_key)],
)


@router.get("", response_model=list[EventResponse])
async def list_events(
    db: Annotated[AsyncSession, Depends(get_db)],
    project_id: UUID | None = None,
    event_type: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    stmt = select(Event)
    if project_id is not None:
        stmt = stmt.where(Event.project_id == project_id)
    if event_type is not None:
        stmt = stmt.where(Event.event_type == event_type)
    result = await db.execute(stmt.order_by(Event.created_at.desc()).limit(limit).offset(offset))
    return result.scalars().all()


@router.post("", response_model=EventResponse, status_code=201)
async def create_event(
    data: EventCreate,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", max_length=255),
    ] = None,
):
    project = await db.get(Project, data.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if idempotency_key is not None:
        idempotency_key = idempotency_key.strip()
        if not idempotency_key:
            raise HTTPException(status_code=422, detail="Idempotency-Key cannot be blank")
        existing = await db.scalar(
            select(Event).where(
                Event.project_id == data.project_id,
                Event.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            response.status_code = 200
            return existing

    event = Event(
        project_id=data.project_id,
        event_type=data.event_type,
        payload=data.payload,
        idempotency_key=idempotency_key,
    )
    db.add(event)

    await db.flush()

    stmt = (
        select(Endpoint)
        .join(Endpoint.subscriptions)
        .where(
            Endpoint.project_id == data.project_id,
            Endpoint.is_active.is_(True),
            or_(
                Subscription.event_type == data.event_type,
                Subscription.event_type == "*",
            ),
        )
        .distinct()
    )
    result = await db.execute(stmt)
    endpoints = result.scalars().all()

    deliveries = [
        Delivery(
            event_id=event.id,
            endpoint_id=endpoint.id,
        )
        for endpoint in endpoints
    ]
    db.add_all(deliveries)

    await db.flush()
    await db.commit()

    for delivery in deliveries:
        deliver_webhook.delay(str(delivery.id))

    await db.refresh(event)

    return event


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(event_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    event = await db.get(Event, event_id)
    if event is None:
        raise HTTPException(
            status_code=404,
            detail="Event not found",
        )

    return event


@router.get("/{event_id}/deliveries", response_model=list[DeliveryResponse])
async def get_event_deliveries(event_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    event = await db.get(Event, event_id)
    if event is None:
        raise HTTPException(
            status_code=404,
            detail="Event not found",
        )

    stmt = select(Delivery).where(Delivery.event_id == event_id).order_by(Delivery.created_at)

    result = await db.execute(stmt)
    deliveries = result.scalars().all()

    return deliveries
