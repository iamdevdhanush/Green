"""Celery background tasks for analytics"""
from datetime import datetime, timezone

from app.workers.celery_app import celery_app
from app.core.logging import get_logger

log = get_logger(__name__)


@celery_app.task(name="app.workers.analytics_worker.aggregate_monthly_task")
def aggregate_monthly_task():
    """Aggregate metrics for the previous month."""
    from app.core.database import SessionLocal
    from app.services.analytics_service import AnalyticsService

    now = datetime.now(timezone.utc)
    # Aggregate previous month
    if now.month == 1:
        year, month = now.year - 1, 12
    else:
        year, month = now.year, now.month - 1

    db = SessionLocal()
    try:
        svc = AnalyticsService(db)
        svc.aggregate_monthly(year, month)
        log.info("monthly_task_complete", year=year, month=month)
    except Exception as e:
        log.error("monthly_task_error", error=str(e))
        raise
    finally:
        db.close()


@celery_app.task(name="app.workers.analytics_worker.mark_offline_machines_task")
def mark_offline_machines_task():
    """Mark stale machines as offline."""
    from app.core.database import SessionLocal
    from app.services.machine_service import MachineService

    db = SessionLocal()
    try:
        svc = MachineService(db)
        count = svc.mark_offline_machines()
        if count:
            log.info("machines_marked_offline", count=count)
    except Exception as e:
        log.error("mark_offline_error", error=str(e))
        raise
    finally:
        db.close()
