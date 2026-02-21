"""Agent registration and heartbeat schemas"""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class AgentRegisterRequest(BaseModel):
    mac_address: str
    hostname: str
    os_version: Optional[str] = None
    cpu_info: Optional[str] = None
    ram_gb: Optional[float] = None
    ip_address: Optional[str] = None

    @field_validator("mac_address")
    @classmethod
    def validate_mac(cls, v: str) -> str:
        v = v.strip().upper().replace("-", ":")
        parts = v.split(":")
        if len(parts) != 6:
            raise ValueError("Invalid MAC address format")
        for part in parts:
            if not all(c in "0123456789ABCDEF" for c in part) or len(part) != 2:
                raise ValueError("Invalid MAC address format")
        return v


class AgentRegisterResponse(BaseModel):
    machine_id: uuid.UUID
    api_key: str
    message: str = "Registration successful"


class HeartbeatRequest(BaseModel):
    idle_minutes: int
    cpu_percent: float
    ram_percent: float
    ip_address: Optional[str] = None


class HeartbeatResponse(BaseModel):
    status: str
    has_pending_command: bool = False
    command_id: Optional[uuid.UUID] = None


class CommandPollResponse(BaseModel):
    has_command: bool
    command_id: Optional[uuid.UUID] = None
    command_type: Optional[str] = None
    idle_threshold_minutes: Optional[int] = None


class CommandResultRequest(BaseModel):
    command_id: uuid.UUID
    executed: bool
    reason: Optional[str] = None
    idle_minutes_at_execution: Optional[int] = None
