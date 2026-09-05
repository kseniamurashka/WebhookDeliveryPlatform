from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DeliveryAttemptResponse(BaseModel):
    id: UUID
    delivery_id: UUID
    status_code: int | None
    response_body: str | None
    error: str | None
    duration_ms: int | None
    started_at: datetime
    finished_at: datetime

    model_config = ConfigDict(from_attributes=True)
