from celery import Celery

from src.core.config import settings

celery_app = Celery(
    "helpdesk_worker",
    broker=settings.celery_broker_url,
    include=["src.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_default_queue="helpdesk_tickets",
)
