import secrets
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_api_key
from app.db.dependencies import get_db
from app.models.endpoint import Endpoint
from app.models.project import Project
from app.schemas.endpoint import EndpointCreate, EndpointCreatedResponse, EndpointResponse

router = APIRouter(
    prefix="/endpoints",
    tags=["Endpoints"],
    dependencies=[Depends(require_api_key)],
)


@router.get("", response_model=list[EndpointResponse])
async def list_endpoints(
    db: Annotated[AsyncSession, Depends(get_db)],
    project_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    stmt = select(Endpoint)
    if project_id is not None:
        stmt = stmt.where(Endpoint.project_id == project_id)
    result = await db.execute(stmt.order_by(Endpoint.created_at.desc()).limit(limit).offset(offset))
    return result.scalars().all()


@router.post("", response_model=EndpointCreatedResponse, status_code=201)
async def create_endpoint(
    data: EndpointCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    project = await db.get(Project, data.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    secret = f"whsec_{secrets.token_urlsafe(32)}"

    endpoint = Endpoint(
        project_id=data.project_id, url=str(data.url), secret=secret, is_active=True
    )

    db.add(endpoint)
    await db.commit()
    await db.refresh(endpoint)

    return endpoint


@router.get("/{endpoint_id}", response_model=EndpointResponse)
async def get_endpoint(
    endpoint_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    endpoint = await db.get(Endpoint, endpoint_id)

    if endpoint is None:
        raise HTTPException(
            status_code=404,
            detail="Endpoint not found",
        )

    return endpoint


@router.patch("/{endpoint_id}/activate", response_model=EndpointResponse)
async def activate_endpoint(
    endpoint_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    endpoint = await db.get(Endpoint, endpoint_id)
    if endpoint is None:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    endpoint.is_active = True
    await db.commit()
    await db.refresh(endpoint)
    return endpoint


@router.post("/{endpoint_id}/rotate-secret", response_model=EndpointCreatedResponse)
async def rotate_endpoint_secret(
    endpoint_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    endpoint = await db.get(Endpoint, endpoint_id)
    if endpoint is None:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    endpoint.secret = f"whsec_{secrets.token_urlsafe(32)}"
    await db.commit()
    await db.refresh(endpoint)
    return endpoint


@router.patch(
    "/{endpoint_id}/deactivate",
    response_model=EndpointResponse,
)
async def deactivate_endpoint(
    endpoint_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    endpoint = await db.get(Endpoint, endpoint_id)

    if endpoint is None:
        raise HTTPException(
            status_code=404,
            detail="Endpoint not found",
        )
    endpoint.is_active = False

    await db.commit()
    await db.refresh(endpoint)

    return endpoint
