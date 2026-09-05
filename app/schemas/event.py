from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EventCreate(BaseModel):
    project_id: UUID
    event_type: str = Field(
        min_length=1,
        max_length=100,
    )
    payload: dict[str, Any]


class EventResponse(BaseModel):
    id: UUID
    project_id: UUID
    event_type: str
    payload: dict[str, Any]
    idempotency_key: str | None
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )
