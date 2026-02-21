"""Shutdown command endpoints"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_admin, get_current_user
from app.services.command_service import CommandService
from app.schemas.command import ShutdownCommandCreate, ShutdownCommandResponse
from app.models.user import User

router = APIRouter(prefix="/commands", tags=["commands"])


@router.post("/shutdown", response_model=ShutdownCommandResponse, status_code=201)
def issue_shutdown(
    data: ShutdownCommandCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Issue a shutdown command. Admin only. Machine must be idle."""
    svc = CommandService(db)
    try:
        cmd = svc.issue_shutdown(
            data=data,
            issued_by_id=current_user.id,
            ip=request.client.host if request.client else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return cmd


@router.get("/shutdown/{machine_id}", response_model=list[ShutdownCommandResponse])
def list_machine_commands(
    machine_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List all shutdown commands for a machine."""
    from sqlalchemy import select, desc
    from app.models.shutdown_command import ShutdownCommand
    cmds = db.execute(
        select(ShutdownCommand)
        .where(ShutdownCommand.machine_id == machine_id)
        .order_by(desc(ShutdownCommand.issued_at))
        .limit(20)
    ).scalars().all()
    return cmds
