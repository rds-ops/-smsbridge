from __future__ import annotations
import logging

from celery import Celery
from celery.signals import worker_ready

from app.core.config import settings

logger = logging.getLogger(__name__)

TASK_MODULES = ("app.jobs.tasks",)

celery_app = Celery(
    "smsbridge",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=list(TASK_MODULES),
)
celery_app.conf.beat_schedule = {
    "poll-waiting-orders": {
        "task": "app.jobs.tasks.poll_waiting_orders",
        "schedule": 5.0,
    },
    "retry-supplier-releases": {
        "task": "app.jobs.tasks.retry_supplier_releases",
        "schedule": 30.0,
    }
}
celery_app.conf.timezone = "UTC"
celery_app.autodiscover_tasks(["app.jobs"])


def registered_smsbridge_tasks() -> list[str]:
    return sorted(name for name in celery_app.tasks if name.startswith("app.jobs."))


@worker_ready.connect
def log_registered_tasks(sender=None, **kwargs) -> None:
    logger.info("smsbridge Celery worker ready. Registered tasks: %s", registered_smsbridge_tasks())
