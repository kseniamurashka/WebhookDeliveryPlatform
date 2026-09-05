import hmac
from typing import Annotated

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.core.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(
    provided_api_key: Annotated[str | None, Security(api_key_header)],
) -> None:
    """Protect management routes when API_KEY is configured."""
    if not settings.api_key:
        return
    if provided_api_key is None or not hmac.compare_digest(
        provided_api_key,
        settings.api_key,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
