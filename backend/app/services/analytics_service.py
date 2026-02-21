"""Analytics aggregation service"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, func, extract
from sqlalchemy.orm import Session

from app.core.redis_client import cache
from app.models.machine import Machine
from app.models.energy_metric import EnergyMetric
from app.models.monthly_analytics import MonthlyAnalytics
from app.schemas.analytics import (
    OverviewStats,
    TimeSeriesPoint,
    CO2TrendResponse,
    CostProjection,
)
from app.utils.calculations import pct_change
from app.core.logging import get_logger

log = get_logger(__name__)


class AnalyticsService:
    def __init__(self, db: Session):
        self.db = db

    def get_overview_stats(self) -> OverviewStats:
        cached = cache.get("overview_stats")
        if cached:
            return OverviewStats(**cached)

        machines = self.db.execute(
            select(Machine).where(Machine.is_active == True)
        ).scalars().all()

        total = len(machines)
        active = sum(1 for m in machines if m.status == "active")
        idle = sum(1 for m in machines if m.status == "idle")
        offline = sum(1 for m in machines if m.status in ("offline", "shutdown"))

        total_kwh = sum(m.total_energy_kwh for m in machines)
        total_co2 = sum(m.total_co2_kg for m in machines)
        total_cost = sum(m.total_cost_usd for m in machines)
        total_idle_hours = sum(m.total_idle_hours for m in machines)

        stats = OverviewStats(
            total_machines=total,
            active_machines=active,
            idle_machines=idle,
            offline_machines=offline,
            total_energy_kwh=round(total_kwh, 3),
            total_co2_kg=round(total_co2, 3),
            total_cost_usd=round(total_cost, 4),
            total_idle_hours=round(total_idle_hours, 2),
        )
        cache.set("overview_stats", stats.model_dump(), ttl=60)
        return stats

    def get_energy_timeseries(self, hours: int = 24) -> list[TimeSeriesPoint]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        # Group by hour
        rows = self.db.execute(
            select(
                func.date_trunc("hour", EnergyMetric.recorded_at).label("hour"),
                func.sum(EnergyMetric.energy_kwh).label("total_kwh"),
            )
            .where(EnergyMetric.recorded_at >= cutoff)
            .group_by("hour")
            .order_by("hour")
        ).all()

        return [
            TimeSeriesPoint(timestamp=row.hour, value=round(row.total_kwh, 4))
            for row in rows
        ]

    def get_co2_trend(self, days: int = 30) -> CO2TrendResponse:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        rows = self.db.execute(
            select(
                func.date_trunc("day", EnergyMetric.recorded_at).label("day"),
                func.sum(EnergyMetric.co2_kg).label("total_co2"),
            )
            .where(EnergyMetric.recorded_at >= cutoff)
            .group_by("day")
            .order_by("day")
        ).all()

        points = [
            TimeSeriesPoint(timestamp=row.day, value=round(row.total_co2, 4))
            for row in rows
        ]
        return CO2TrendResponse(points=points)

    def get_cost_projection(self) -> CostProjection:
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        current_cost = self.db.execute(
            select(func.sum(EnergyMetric.cost_usd))
            .where(EnergyMetric.recorded_at >= month_start)
        ).scalar() or 0.0

        # Days elapsed and remaining
        days_elapsed = (now - month_start).days + 1
        total_days = 30
        days_remaining = total_days - days_elapsed

        daily_rate = current_cost / max(days_elapsed, 1)
        projected = current_cost + (daily_rate * days_remaining)
        savings = projected * 0.35  # 35% potential via shutdowns

        return CostProjection(
            current_month_cost=round(current_cost, 4),
            projected_month_cost=round(projected, 4),
            potential_savings=round(savings, 4),
            savings_percentage=35.0,
        )

    def aggregate_monthly(self, year: int, month: int) -> None:
        """Aggregate all machine metrics for a given month."""
        from calendar import monthrange
        from datetime import date

        start = datetime(year, month, 1, tzinfo=timezone.utc)
        _, last_day = monthrange(year, month)
        end = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)

        machines = self.db.execute(
            select(Machine).where(Machine.is_active == True)
        ).scalars().all()

        for machine in machines:
            rows = self.db.execute(
                select(
                    func.sum(EnergyMetric.energy_kwh).label("kwh"),
                    func.sum(EnergyMetric.co2_kg).label("co2"),
                    func.sum(EnergyMetric.cost_usd).label("cost"),
                    func.sum(EnergyMetric.idle_minutes).label("idle_min"),
                )
                .where(
                    EnergyMetric.machine_id == machine.id,
                    EnergyMetric.recorded_at >= start,
                    EnergyMetric.recorded_at <= end,
                )
            ).one()

            kwh = rows.kwh or 0.0
            co2 = rows.co2 or 0.0
            cost = rows.cost or 0.0
            idle_hours = (rows.idle_min or 0) / 60

            # Get previous month stats for comparison
            prev_month = month - 1 if month > 1 else 12
            prev_year = year if month > 1 else year - 1
            prev = self.db.execute(
                select(MonthlyAnalytics).where(
                    MonthlyAnalytics.machine_id == machine.id,
                    MonthlyAnalytics.year == prev_year,
                    MonthlyAnalytics.month == prev_month,
                )
            ).scalar_one_or_none()

            existing = self.db.execute(
                select(MonthlyAnalytics).where(
                    MonthlyAnalytics.machine_id == machine.id,
                    MonthlyAnalytics.year == year,
                    MonthlyAnalytics.month == month,
                )
            ).scalar_one_or_none()

            if existing:
                existing.total_kwh = kwh
                existing.total_co2_kg = co2
                existing.total_cost_usd = cost
                existing.total_idle_hours = idle_hours
                existing.aggregated_at = datetime.now(timezone.utc)
                if prev:
                    existing.kwh_change_pct = pct_change(kwh, prev.total_kwh)
                    existing.co2_change_pct = pct_change(co2, prev.total_co2_kg)
                    existing.cost_change_pct = pct_change(cost, prev.total_cost_usd)
            else:
                record = MonthlyAnalytics(
                    machine_id=machine.id,
                    year=year,
                    month=month,
                    total_kwh=kwh,
                    total_co2_kg=co2,
                    total_cost_usd=cost,
                    total_idle_hours=idle_hours,
                    kwh_change_pct=pct_change(kwh, prev.total_kwh) if prev else None,
                    co2_change_pct=pct_change(co2, prev.total_co2_kg) if prev else None,
                    cost_change_pct=pct_change(cost, prev.total_cost_usd) if prev else None,
                )
                self.db.add(record)

        self.db.commit()
        log.info("monthly_aggregation_complete", year=year, month=month)

    def get_monthly_reports(self, year: Optional[int] = None) -> list[MonthlyAnalytics]:
        now = datetime.now(timezone.utc)
        target_year = year or now.year

        return self.db.execute(
            select(MonthlyAnalytics)
            .where(
                MonthlyAnalytics.machine_id.is_(None) | (MonthlyAnalytics.year == target_year),
                MonthlyAnalytics.year == target_year,
            )
            .order_by(MonthlyAnalytics.month.desc())
        ).scalars().all()
