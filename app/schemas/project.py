from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=100,
    )


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )
