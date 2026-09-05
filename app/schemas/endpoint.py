from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, HttpUrl


class EndpointCreate(BaseModel):
    project_id: UUID
    url: HttpUrl  # не str, чтобы Pydantic сам проверил корректность url


class EndpointResponse(BaseModel):
    id: UUID
    project_id: UUID
    url: HttpUrl
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Формат ответа при регистрации Endpoint
# Пользователь увидит сформированный сервером secret и должен сохранить его
# для дальнейшей проверки webhook-запросов.
class EndpointCreatedResponse(EndpointResponse):
    id: UUID
    project_id: UUID
    url: HttpUrl
    is_active: bool
    created_at: datetime
    secret: str

    model_config = ConfigDict(from_attributes=True)
