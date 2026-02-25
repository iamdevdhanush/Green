"""GreenOps Agents Router"""
import re
from datetime import datetime, timezone
from typing import Optional
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import AgentToken, Heartbeat, Machine, MachineStatus, get_db
from utils.auth import generate_agent_token, hash_agent_token
from utils.energy import calculate_energy_wasted, calculate_cost, is_idle
from utils.security import get_current_machine

logger = structlog.get_logger(__name__)
router = APIRouter()
MAC_REGEX = re.compile(r"^([0-9A-Fa-f]{2}[:\-]){5}([0-9A-Fa-f]{2})$")


class RegisterRequest(BaseModel):
    mac_address: str = Field(..., min_length=17, max_length=17)
    hostname: str = Field(..., min_length=1, max_length=255)
    os_type: str = Field(..., min_length=1, max_length=64)
    os_version: Optional[str] = Field(None, max_length=128)
    agent_version: Optional[str] = Field(None, max_length=32)

    @field_validator("mac_address")
    @classmethod
    def validate_mac(cls, v: str) -> str:
        normalized = v.upper().replace("-", ":")
        if not MAC_REGEX.match(normalized):
            raise ValueError("Invalid MAC address format")
        return normalized

    @field_validator("hostname")
    @classmethod
    def sanitize_hostname(cls, v: str) -> str:
        sanitized = re.sub(r"[^a-zA-Z0-9\-_.]", "", v.strip())
        if not sanitized:
            raise ValueError("Invalid hostname")
        return sanitized[:255]


class RegisterResponse(BaseModel):
    token: str
    machine_id: int
    message: str


class HeartbeatRequest(BaseModel):
    idle_seconds: int = Field(..., ge=0, le=86400)
    cpu_usage: Optional[float] = Field(None, ge=0.0, le=100.0)
    memory_usage: Optional[float] = Field(None, ge=0.0, le=100.0)
    timestamp: Optional[datetime] = None
    ip_address: Optional[str] = Field(None, max_length=64)


class HeartbeatResponse(BaseModel):
    status: str
    machine_status: str
    energy_wasted_kwh: float


@router.post("/register", response_model=RegisterResponse)
async def register_agent(payload: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or (
        request.client.host if request.client else None
    )

    result = await db.execute(select(Machine).where(Machine.mac_address == payload.mac_address))
    machine = result.scalar_one_or_none()

    if machine:
        machine.hostname = payload.hostname
        machine.os_type = payload.os_type
        machine.os_version = payload.os_version
        machine.agent_version = payload.agent_version
        machine.ip_address = client_ip
        machine.last_seen = datetime.now(timezone.utc)
        machine.status = MachineStatus.ONLINE

        result = await db.execute(
            select(AgentToken).where(AgentToken.machine_id == machine.id, AgentToken.revoked == False)
        )
        agent_token = result.scalar_one_or_none()
        raw_token, token_hash = generate_agent_token()
        if not agent_token:
            agent_token = AgentToken(machine_id=machine.id, token_hash=token_hash)
            db.add(agent_token)
        else:
            agent_token.token_hash = token_hash

        await db.commit()
        logger.info("agent_re_registered", machine_id=machine.id)
        return RegisterResponse(token=raw_token, machine_id=machine.id, message="Machine re-registered successfully")

    machine = Machine(
        mac_address=payload.mac_address,
        hostname=payload.hostname,
        os_type=payload.os_type,
        os_version=payload.os_version,
        agent_version=payload.agent_version,
        ip_address=client_ip,
        status=MachineStatus.ONLINE,
    )
    db.add(machine)
    await db.flush()

    raw_token, token_hash = generate_agent_token()
    agent_token = AgentToken(machine_id=machine.id, token_hash=token_hash)
    db.add(agent_token)
    await db.commit()

    logger.info("agent_registered", machine_id=machine.id, hostname=machine.hostname)
    return RegisterResponse(token=raw_token, machine_id=machine.id, message="Machine registered successfully")


@router.post("/heartbeat", response_model=HeartbeatResponse)
async def submit_heartbeat(
    payload: HeartbeatRequest,
    machine: Machine = Depends(get_current_machine),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    machine_is_idle = is_idle(payload.idle_seconds)
    machine.last_seen = now
    machine.status = MachineStatus.IDLE if machine_is_idle else MachineStatus.ONLINE

    energy_delta = calculate_energy_wasted(payload.idle_seconds)
    cost_delta = calculate_cost(energy_delta)

    machine.total_idle_seconds += payload.idle_seconds
    machine.energy_wasted_kwh += energy_delta
    machine.energy_cost_usd += cost_delta

    if payload.ip_address:
        machine.ip_address = payload.ip_address[:64]

    heartbeat = Heartbeat(
        machine_id=machine.id,
        timestamp=payload.timestamp or now,
        idle_seconds=payload.idle_seconds,
        cpu_usage=payload.cpu_usage,
        memory_usage=payload.memory_usage,
        is_idle=machine_is_idle,
        energy_delta_kwh=energy_delta,
    )
    db.add(heartbeat)
    await db.commit()

    return HeartbeatResponse(status="ok", machine_status=machine.status.value, energy_wasted_kwh=machine.energy_wasted_kwh)


@router.get("/health")
async def agent_health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
