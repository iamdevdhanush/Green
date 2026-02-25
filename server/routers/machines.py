"""GreenOps Machines Router"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from config import get_settings
from database import AgentToken, Heartbeat, Machine, MachineStatus, get_db
from utils.security import get_current_user, require_admin

logger = structlog.get_logger(__name__)
router = APIRouter()
settings = get_settings()


class MachineOut(BaseModel):
    id: int
    mac_address: str
    hostname: str
    os_type: str
    os_version: Optional[str]
    ip_address: Optional[str]
    status: str
    first_seen: datetime
    last_seen: datetime
    total_idle_seconds: int
    total_active_seconds: int
    energy_wasted_kwh: float
    energy_cost_usd: float
    agent_version: Optional[str]
    notes: Optional[str]

    class Config:
        from_attributes = True


class HeartbeatOut(BaseModel):
    id: int
    timestamp: datetime
    idle_seconds: int
    cpu_usage: Optional[float]
    memory_usage: Optional[float]
    is_idle: bool
    energy_delta_kwh: float

    class Config:
        from_attributes = True


class UpdateMachineRequest(BaseModel):
    notes: Optional[str] = Field(None, max_length=1000)
    hostname: Optional[str] = Field(None, min_length=1, max_length=255)


async def mark_offline_machines(db: AsyncSession):
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.OFFLINE_THRESHOLD_SECONDS)
    result = await db.execute(
        select(Machine).where(
            Machine.status.in_([MachineStatus.ONLINE, MachineStatus.IDLE]),
            Machine.last_seen < cutoff,
        )
    )
    machines = result.scalars().all()
    for m in machines:
        m.status = MachineStatus.OFFLINE
    if machines:
        await db.commit()


@router.get("", response_model=List[MachineOut])
async def list_machines(
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None, max_length=100),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await mark_offline_machines(db)
    query = select(Machine)
    if status_filter:
        try:
            status_enum = MachineStatus(status_filter.lower())
            query = query.where(Machine.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail={"error": "invalid_filter", "message": f"Invalid status: {status_filter}"})
    if search:
        term = f"%{search}%"
        query = query.where(Machine.hostname.ilike(term) | Machine.mac_address.ilike(term) | Machine.ip_address.ilike(term))
    query = query.order_by(desc(Machine.last_seen)).limit(limit).offset(offset)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/count")
async def count_machines(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await mark_offline_machines(db)
    result = await db.execute(select(Machine.status, func.count(Machine.id)).group_by(Machine.status))
    counts = {row[0].value: row[1] for row in result.all()}
    return {"total": sum(counts.values()), "online": counts.get("online", 0), "idle": counts.get("idle", 0), "offline": counts.get("offline", 0)}


@router.get("/{machine_id}", response_model=MachineOut)
async def get_machine(machine_id: int, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Machine).where(Machine.id == machine_id))
    machine = result.scalar_one_or_none()
    if not machine:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Machine not found."})
    return machine


@router.patch("/{machine_id}", response_model=MachineOut)
async def update_machine(machine_id: int, payload: UpdateMachineRequest, current_user=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Machine).where(Machine.id == machine_id))
    machine = result.scalar_one_or_none()
    if not machine:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Machine not found."})
    if payload.notes is not None:
        machine.notes = payload.notes
    if payload.hostname is not None:
        machine.hostname = payload.hostname
    await db.commit()
    return machine


@router.delete("/{machine_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_machine(machine_id: int, current_user=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Machine).where(Machine.id == machine_id))
    machine = result.scalar_one_or_none()
    if not machine:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Machine not found."})
    await db.delete(machine)
    await db.commit()


@router.get("/{machine_id}/heartbeats", response_model=List[HeartbeatOut])
async def get_machine_heartbeats(machine_id: int, limit: int = Query(100, ge=1, le=1000), current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Machine).where(Machine.id == machine_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Machine not found."})
    result = await db.execute(select(Heartbeat).where(Heartbeat.machine_id == machine_id).order_by(desc(Heartbeat.timestamp)).limit(limit))
    return result.scalars().all()


@router.post("/{machine_id}/revoke-token", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_agent_token(machine_id: int, current_user=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AgentToken).where(AgentToken.machine_id == machine_id, AgentToken.revoked == False))
    token = result.scalar_one_or_none()
    if token:
        token.revoked = True
        await db.commit()
