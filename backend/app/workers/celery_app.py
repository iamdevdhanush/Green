"""Celery configuration and task registration"""
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "greenops",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.analytics_worker"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    beat_schedule={
        # Aggregate monthly analytics at midnight on the 1st of each month
        "aggregate-monthly": {
            "task": "app.workers.analytics_worker.aggregate_monthly_task",
            "schedule": crontab(hour=0, minute=5, day_of_month=1),
        },
        # Mark offline machines every 5 minutes
        "mark-offline": {
            "task": "app.workers.analytics_worker.mark_offline_machines_task",
            "schedule": crontab(minute="*/5"),
        },
    },
)
