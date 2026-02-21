"""Agent API endpoints - registration, heartbeat, command polling"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, status, Header
from typing import Optional
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.machine_service import MachineService
from app.services.command_service import CommandService
from app.schemas.agent import (
    AgentRegisterRequest,
    AgentRegisterResponse,
    HeartbeatRequest,
    HeartbeatResponse,
    CommandPollResponse,
    CommandResultRequest,
)

router = APIRouter(prefix="/agents", tags=["agents"])


def get_machine_from_api_key(
    x_api_key: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-Key header required")

    svc = MachineService(db)
    machine = svc.get_machine_by_api_key(x_api_key)
    if not machine:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return machine


@router.post("/register", response_model=AgentRegisterResponse, status_code=201)
def register_agent(
    data: AgentRegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Register a new machine agent.
    MAC address is the unique device identifier.
    Prevents duplicate registrations.
    """
    svc = MachineService(db)
    machine, is_new = svc.register_agent(data)

    return AgentRegisterResponse(
        machine_id=machine.id,
        api_key=machine.api_key,
        message="Registration successful" if is_new else "Re-registration successful",
    )


@router.post("/heartbeat", response_model=HeartbeatResponse)
def heartbeat(
    data: HeartbeatRequest,
    db: Session = Depends(get_db),
    machine=Depends(get_machine_from_api_key),
):
    """Receive machine telemetry and return pending command flag."""
    svc = MachineService(db)
    svc.process_heartbeat(machine, data)

    cmd_svc = CommandService(db)
    cmd = cmd_svc.get_pending_command(machine.id)

    return HeartbeatResponse(
        status="ok",
        has_pending_command=cmd is not None,
        command_id=cmd.id if cmd else None,
    )


@router.get("/commands/poll", response_model=CommandPollResponse)
def poll_commands(
    db: Session = Depends(get_db),
    machine=Depends(get_machine_from_api_key),
):
    """Poll for pending shutdown commands."""
    cmd_svc = CommandService(db)
    cmd = cmd_svc.get_pending_command(machine.id)

    if not cmd:
        return CommandPollResponse(has_command=False)

    return CommandPollResponse(
        has_command=True,
        command_id=cmd.id,
        command_type="shutdown",
        idle_threshold_minutes=cmd.idle_threshold_minutes,
    )


@router.post("/commands/result")
def command_result(
    data: CommandResultRequest,
    db: Session = Depends(get_db),
    machine=Depends(get_machine_from_api_key),
):
    """Report the result of a shutdown command execution."""
    cmd_svc = CommandService(db)
    try:
        cmd = cmd_svc.process_command_result(
            command_id=data.command_id,
            machine_id=machine.id,
            executed=data.executed,
            reason=data.reason,
            idle_minutes=data.idle_minutes_at_execution,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"status": "recorded", "command_status": cmd.status}
