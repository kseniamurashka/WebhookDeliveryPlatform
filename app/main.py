from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.deliveries import router as delivery_router
from app.api.endpoints import router as endpoint_router
from app.api.events import router as event_router
from app.api.health import router as health_router
from app.api.projects import router as project_router
from app.api.subscriptions import router as subscription_router
from app.api.test_webhooks import router as webhook_router
from app.core.config import settings
from app.db.session import engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    summary="Reliable asynchronous webhook delivery",
    description=(
        "Register endpoints and subscriptions, publish events, and inspect every "
        "signed delivery attempt. Failed transient requests are retried with "
        "exponential backoff."
    ),
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(project_router)
app.include_router(endpoint_router)
app.include_router(subscription_router)
app.include_router(event_router)
app.include_router(delivery_router)
app.include_router(webhook_router)


@app.get("/", include_in_schema=False)
async def index():
    return {
        "name": settings.app_name,
        "version": app.version,
        "documentation": "/docs",
        "health": "/health/ready",
    }
