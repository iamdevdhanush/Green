"""Machine management endpoints"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user, require_manager_or_above
from app.services.machine_service import MachineService
from app.schemas.machine import MachineResponse, MachineListResponse, EnergyMetricResponse
from app.utils.pagination import pagination_params, PaginationParams
from app.models.user import User

router = APIRouter(prefix="/machines", tags=["machines"])


@router.get("", response_model=MachineListResponse)
def list_machines(
    status: Optional[str] = Query(None, description="Filter by status: active|idle|offline"),
    search: Optional[str] = Query(None),
    pagination: PaginationParams = Depends(pagination_params),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    svc = MachineService(db)
    machines, total = svc.list_machines(pagination, status, search)
    return MachineListResponse(
        total=total,
        page=pagination.page,
        per_page=pagination.per_page,
        machines=machines,
    )


@router.get("/{machine_id}", response_model=MachineResponse)
def get_machine(
    machine_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    svc = MachineService(db)
    machine = svc.get_machine(machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")
    return machine


@router.get("/{machine_id}/history", response_model=list[EnergyMetricResponse])
def get_machine_history(
    machine_id: uuid.UUID,
    hours: int = Query(default=24, ge=1, le=720),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    svc = MachineService(db)
    machine = svc.get_machine(machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")
    return svc.get_machine_history(machine_id, hours)


@router.delete("/{machine_id}", status_code=204)
def deactivate_machine(
    machine_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
):
    svc = MachineService(db)
    machine = svc.get_machine(machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")
    machine.is_active = False
    db.commit()
    return None
