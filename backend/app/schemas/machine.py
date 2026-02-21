"""Machine Pydantic schemas"""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class MachineResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    mac_address: str
    hostname: str
    os_version: Optional[str] = None
    cpu_info: Optional[str] = None
    ram_gb: Optional[float] = None
    ip_address: Optional[str] = None
    status: str
    idle_minutes: int
    total_idle_hours: float
    total_energy_kwh: float
    total_co2_kg: float
    total_cost_usd: float
    last_seen: Optional[datetime] = None
    registered_at: datetime
    is_active: bool


class MachineUpdate(BaseModel):
    hostname: Optional[str] = None
    is_active: Optional[bool] = None


class MachineListResponse(BaseModel):
    total: int
    page: int
    per_page: int
    machines: list[MachineResponse]


class EnergyMetricResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    machine_id: uuid.UUID
    idle_minutes: int
    cpu_percent: float
    ram_percent: float
    energy_kwh: float
    co2_kg: float
    cost_usd: float
    recorded_at: datetime
