from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.delivery_attempt import DeliveryAttempt
    from app.models.endpoint import Endpoint
    from app.models.event import Event


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    RETRYING = "retrying"
    DEAD = "dead"


class Delivery(Base):
    __tablename__ = "deliveries"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("events.id"),
        nullable=False,
        index=True,
    )

    endpoint_id: Mapped[UUID] = mapped_column(
        ForeignKey("endpoints.id"),
        nullable=False,
        index=True,
    )

    status: Mapped[DeliveryStatus] = mapped_column(
        SAEnum(DeliveryStatus),
        default=DeliveryStatus.PENDING,
        nullable=False,
    )

    attempt_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    event: Mapped["Event"] = relationship(back_populates="deliveries")
    endpoint: Mapped["Endpoint"] = relationship(back_populates="deliveries")
    attempts: Mapped[list["DeliveryAttempt"]] = relationship(back_populates="delivery")
