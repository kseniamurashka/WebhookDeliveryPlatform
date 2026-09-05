from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "webhooks",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    broker_connection_retry_on_startup=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
    timezone="UTC",
)
