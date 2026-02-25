"""
GreenOps Dashboard Router
- Aggregate statistics
- Energy trends
- Top idle machines
"""
from datetime import datetime, timedelta, timezone
from typing import List

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database import Heartbeat, Machine, MachineStatus, get_db
from utils.security import get_current_user

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/stats")
async def get_stats(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get aggregate dashboard statistics."""
    # Machine counts by status
    status_counts = await db.execute(
        select(Machine.status, func.count(Machine.id)).group_by(Machine.status)
    )
    counts = {row[0].value: row[1] for row in status_counts.all()}
    total = sum(counts.values())

    # Energy totals
    energy_result = await db.execute(
        select(
            func.sum(Machine.energy_wasted_kwh),
            func.sum(Machine.energy_cost_usd),
            func.sum(Machine.total_idle_seconds),
            func.sum(Machine.total_active_seconds),
        )
    )
    energy_row = energy_result.first()
    total_energy = float(energy_row[0] or 0)
    total_cost = float(energy_row[1] or 0)
    total_idle = int(energy_row[2] or 0)
    total_active = int(energy_row[3] or 0)

    # Average idle percentage
    total_time = total_idle + total_active
    avg_idle_pct = (total_idle / total_time * 100) if total_time > 0 else 0.0

    # Machines seen in last 24h
    cutoff_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    active_24h_result = await db.execute(
        select(func.count(Machine.id)).where(Machine.last_seen >= cutoff_24h)
    )
    active_24h = active_24h_result.scalar() or 0

    return {
        "total_machines": total,
        "online_machines": counts.get("online", 0),
        "idle_machines": counts.get("idle", 0),
        "offline_machines": counts.get("offline", 0),
        "active_last_24h": active_24h,
        "total_energy_wasted_kwh": round(total_energy, 3),
        "estimated_cost_usd": round(total_cost, 2),
        "average_idle_percentage": round(avg_idle_pct, 1),
        "total_idle_hours": round(total_idle / 3600, 1),
    }


@router.get("/energy-trend")
async def get_energy_trend(
    days: int = Query(7, ge=1, le=90),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get energy waste trend over the past N days."""
    from sqlalchemy import cast, Date
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(
            func.date_trunc("day", Heartbeat.timestamp).label("day"),
            func.sum(Heartbeat.energy_delta_kwh).label("energy_kwh"),
            func.count(Heartbeat.id).label("heartbeat_count"),
            func.avg(Heartbeat.cpu_usage).label("avg_cpu"),
            func.avg(Heartbeat.memory_usage).label("avg_memory"),
        )
        .where(Heartbeat.timestamp >= cutoff)
        .group_by(func.date_trunc("day", Heartbeat.timestamp))
        .order_by(func.date_trunc("day", Heartbeat.timestamp))
    )

    trend = []
    for row in result.all():
        trend.append({
            "date": row.day.date().isoformat() if row.day else None,
            "energy_kwh": round(float(row.energy_kwh or 0), 4),
            "heartbeat_count": int(row.heartbeat_count or 0),
            "avg_cpu": round(float(row.avg_cpu or 0), 1) if row.avg_cpu else None,
            "avg_memory": round(float(row.avg_memory or 0), 1) if row.avg_memory else None,
        })

    return {"days": days, "data": trend}


@router.get("/top-idle")
async def get_top_idle_machines(
    limit: int = Query(10, ge=1, le=50),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get top machines by idle time."""
    result = await db.execute(
        select(Machine)
        .where(Machine.total_idle_seconds > 0)
        .order_by(desc(Machine.energy_wasted_kwh))
        .limit(limit)
    )
    machines = result.scalars().all()

    return [
        {
            "id": m.id,
            "hostname": m.hostname,
            "status": m.status.value,
            "total_idle_hours": round(m.total_idle_seconds / 3600, 1),
            "energy_wasted_kwh": round(m.energy_wasted_kwh, 3),
            "energy_cost_usd": round(m.energy_cost_usd, 2),
            "os_type": m.os_type,
        }
        for m in machines
    ]


@router.get("/recent-activity")
async def get_recent_activity(
    limit: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get recent heartbeats across all machines."""
    result = await db.execute(
        select(Heartbeat, Machine.hostname, Machine.os_type)
        .join(Machine, Heartbeat.machine_id == Machine.id)
        .order_by(desc(Heartbeat.timestamp))
        .limit(limit)
    )

    activity = []
    for heartbeat, hostname, os_type in result.all():
        activity.append({
            "machine_id": heartbeat.machine_id,
            "hostname": hostname,
            "os_type": os_type,
            "timestamp": heartbeat.timestamp,
            "is_idle": heartbeat.is_idle,
            "idle_seconds": heartbeat.idle_seconds,
            "cpu_usage": heartbeat.cpu_usage,
            "memory_usage": heartbeat.memory_usage,
        })

    return activity
