"""Analytics schemas"""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class OverviewStats(BaseModel):
    total_machines: int
    active_machines: int
    idle_machines: int
    offline_machines: int
    total_energy_kwh: float
    total_co2_kg: float
    total_cost_usd: float
    total_idle_hours: float


class MonthlyAnalyticsResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    machine_id: Optional[uuid.UUID] = None
    year: int
    month: int
    total_kwh: float
    total_co2_kg: float
    total_cost_usd: float
    total_idle_hours: float
    kwh_change_pct: Optional[float] = None
    co2_change_pct: Optional[float] = None
    cost_change_pct: Optional[float] = None
    aggregated_at: datetime


class TimeSeriesPoint(BaseModel):
    timestamp: datetime
    value: float
    label: Optional[str] = None


class CO2TrendResponse(BaseModel):
    points: list[TimeSeriesPoint]
    unit: str = "kg"


class CostProjection(BaseModel):
    current_month_cost: float
    projected_month_cost: float
    potential_savings: float
    savings_percentage: float


class AuditLogResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    machine_id: Optional[uuid.UUID] = None
    action: str
    resource_type: Optional[str] = None
    details: Optional[dict] = None
    ip_address: Optional[str] = None
    created_at: datetime
