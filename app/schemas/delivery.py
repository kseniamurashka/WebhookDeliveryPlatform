from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.delivery import DeliveryStatus


class DeliveryResponse(BaseModel):
    id: UUID
    event_id: UUID
    endpoint_id: UUID
    status: DeliveryStatus
    attempt_count: int
    next_attempt_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
