"""Shutdown command service"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.machine import Machine
from app.models.shutdown_command import ShutdownCommand
from app.models.audit_log import AuditLog
from app.schemas.command import ShutdownCommandCreate
from app.core.logging import get_logger

log = get_logger(__name__)


class CommandService:
    def __init__(self, db: Session):
        self.db = db

    def issue_shutdown(
        self, data: ShutdownCommandCreate, issued_by_id: uuid.UUID, ip: str = None
    ) -> ShutdownCommand:
        machine = self.db.get(Machine, data.machine_id)
        if not machine:
            raise ValueError("Machine not found")

        if machine.status not in ("idle",):
            raise ValueError(
                f"Shutdown only allowed for idle machines. Current status: {machine.status}"
            )

        # Cancel any existing pending commands for this machine
        existing = self.db.execute(
            select(ShutdownCommand).where(
                ShutdownCommand.machine_id == data.machine_id,
                ShutdownCommand.status == "pending",
            )
        ).scalars().all()
        for cmd in existing:
            cmd.status = "expired"

        now = datetime.now(timezone.utc)
        cmd = ShutdownCommand(
            machine_id=data.machine_id,
            issued_by=issued_by_id,
            status="pending",
            idle_threshold_minutes=data.idle_threshold_minutes,
            notes=data.notes,
            expires_at=now + timedelta(seconds=settings.SHUTDOWN_COMMAND_TTL_SECONDS),
        )
        self.db.add(cmd)

        # Audit log
        audit = AuditLog(
            user_id=issued_by_id,
            machine_id=data.machine_id,
            action="shutdown_command_issued",
            resource_type="shutdown_command",
            resource_id=str(cmd.id),
            details={"threshold": data.idle_threshold_minutes, "notes": data.notes},
            ip_address=ip,
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(cmd)

        log.info(
            "shutdown_issued",
            machine_id=str(data.machine_id),
            by=str(issued_by_id),
        )
        return cmd

    def get_pending_command(self, machine_id: uuid.UUID) -> Optional[ShutdownCommand]:
        """Get the latest pending command for a machine. Auto-expire stale ones."""
        now = datetime.now(timezone.utc)

        # Expire overdue commands
        stale = self.db.execute(
            select(ShutdownCommand).where(
                ShutdownCommand.machine_id == machine_id,
                ShutdownCommand.status == "pending",
                ShutdownCommand.expires_at < now,
            )
        ).scalars().all()
        for s in stale:
            s.status = "expired"
        if stale:
            self.db.commit()

        return self.db.execute(
            select(ShutdownCommand).where(
                ShutdownCommand.machine_id == machine_id,
                ShutdownCommand.status == "pending",
                ShutdownCommand.expires_at >= now,
            )
        ).scalar_one_or_none()

    def process_command_result(
        self,
        command_id: uuid.UUID,
        machine_id: uuid.UUID,
        executed: bool,
        reason: Optional[str] = None,
        idle_minutes: Optional[int] = None,
    ) -> ShutdownCommand:
        cmd = self.db.get(ShutdownCommand, command_id)
        if not cmd or cmd.machine_id != machine_id:
            raise ValueError("Command not found")

        now = datetime.now(timezone.utc)
        if executed:
            cmd.status = "executed"
            cmd.executed_at = now

            machine = self.db.get(Machine, machine_id)
            if machine:
                machine.status = "shutdown"

            audit_action = "shutdown_executed"
        else:
            cmd.status = "rejected"
            cmd.rejection_reason = reason
            audit_action = "shutdown_rejected"

        audit = AuditLog(
            machine_id=machine_id,
            action=audit_action,
            resource_type="shutdown_command",
            resource_id=str(command_id),
            details={
                "executed": executed,
                "reason": reason,
                "idle_minutes": idle_minutes,
            },
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(cmd)

        log.info(
            "command_result",
            command_id=str(command_id),
            executed=executed,
            reason=reason,
        )
        return cmd
