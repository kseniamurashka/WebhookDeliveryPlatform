from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SubscriptionCreate(BaseModel):
    endpoint_id: UUID
    event_type: str = Field(
        min_length=1,
        max_length=100,
    )


class SubscriptionResponse(BaseModel):
    id: UUID
    endpoint_id: UUID
    event_type: str
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )
