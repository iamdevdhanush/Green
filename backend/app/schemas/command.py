"""Shutdown command schemas"""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ShutdownCommandCreate(BaseModel):
    machine_id: uuid.UUID
    idle_threshold_minutes: int = 15
    notes: Optional[str] = None


class ShutdownCommandResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    machine_id: uuid.UUID
    issued_by: uuid.UUID
    status: str
    idle_threshold_minutes: int
    rejection_reason: Optional[str] = None
    notes: Optional[str] = None
    issued_at: datetime
    expires_at: datetime
    executed_at: Optional[datetime] = None
