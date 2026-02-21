"""Analytics endpoints"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.services.analytics_service import AnalyticsService
from app.schemas.analytics import (
    OverviewStats,
    CO2TrendResponse,
    CostProjection,
    MonthlyAnalyticsResponse,
    TimeSeriesPoint,
    AuditLogResponse,
)
from app.models.user import User

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=OverviewStats)
def overview(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get platform-wide overview statistics."""
    svc = AnalyticsService(db)
    return svc.get_overview_stats()


@router.get("/energy/timeseries", response_model=list[TimeSeriesPoint])
def energy_timeseries(
    hours: int = Query(default=24, ge=1, le=720),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Energy consumption time series, grouped by hour."""
    svc = AnalyticsService(db)
    return svc.get_energy_timeseries(hours)


@router.get("/co2/trend", response_model=CO2TrendResponse)
def co2_trend(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """CO₂ emissions trend by day."""
    svc = AnalyticsService(db)
    return svc.get_co2_trend(days)


@router.get("/cost/projection", response_model=CostProjection)
def cost_projection(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Current month cost and projected end-of-month cost."""
    svc = AnalyticsService(db)
    return svc.get_cost_projection()


@router.get("/monthly", response_model=list[MonthlyAnalyticsResponse])
def monthly_reports(
    year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Pre-aggregated monthly analytics."""
    svc = AnalyticsService(db)
    return svc.get_monthly_reports(year)


@router.get("/audit", response_model=list[AuditLogResponse])
def audit_logs(
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Recent audit log entries."""
    from sqlalchemy import select, desc
    from app.models.audit_log import AuditLog
    logs = db.execute(
        select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit)
    ).scalars().all()
    return logs
