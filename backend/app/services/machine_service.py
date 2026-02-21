"""Machine management service"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session

from app.core.security import generate_api_key
from app.core.redis_client import cache
from app.models.machine import Machine
from app.models.energy_metric import EnergyMetric
from app.schemas.agent import AgentRegisterRequest, HeartbeatRequest
from app.utils.calculations import calculate_all
from app.utils.pagination import PaginationParams
from app.core.logging import get_logger

log = get_logger(__name__)


class MachineService:
    def __init__(self, db: Session):
        self.db = db

    def register_agent(self, data: AgentRegisterRequest) -> tuple[Machine, bool]:
        """
        Register or re-register a machine.
        Returns (machine, is_new).
        """
        existing = self.db.execute(
            select(Machine).where(Machine.mac_address == data.mac_address)
        ).scalar_one_or_none()

        if existing:
            # Update last-seen metadata on re-registration
            existing.hostname = data.hostname
            existing.os_version = data.os_version
            existing.cpu_info = data.cpu_info
            existing.ram_gb = data.ram_gb
            existing.ip_address = data.ip_address
            existing.last_seen = datetime.now(timezone.utc)
            existing.status = "active"
            self.db.commit()
            self.db.refresh(existing)
            log.info("agent_re_registered", mac=data.mac_address)
            return existing, False

        machine = Machine(
            mac_address=data.mac_address,
            hostname=data.hostname,
            os_version=data.os_version,
            cpu_info=data.cpu_info,
            ram_gb=data.ram_gb,
            ip_address=data.ip_address,
            api_key=generate_api_key(),
            status="active",
            last_seen=datetime.now(timezone.utc),
        )
        self.db.add(machine)
        self.db.commit()
        self.db.refresh(machine)
        log.info("agent_registered", mac=data.mac_address, machine_id=str(machine.id))
        return machine, True

    def process_heartbeat(self, machine: Machine, data: HeartbeatRequest) -> None:
        """Update machine state and record energy metric."""
        now = datetime.now(timezone.utc)

        # Update machine
        machine.idle_minutes = data.idle_minutes
        machine.last_seen = now
        if data.ip_address:
            machine.ip_address = data.ip_address

        # Determine status
        if data.idle_minutes >= 15:
            machine.status = "idle"
        else:
            machine.status = "active"

        # Calculate incremental energy (assuming 60s polling interval)
        interval_idle_minutes = min(data.idle_minutes, 1)  # 1 min per heartbeat
        energy = calculate_all(interval_idle_minutes)

        machine.total_idle_hours += interval_idle_minutes / 60
        machine.total_energy_kwh += energy["energy_kwh"]
        machine.total_co2_kg += energy["co2_kg"]
        machine.total_cost_usd += energy["cost_usd"]

        # Record metric
        metric = EnergyMetric(
            machine_id=machine.id,
            idle_minutes=data.idle_minutes,
            cpu_percent=data.cpu_percent,
            ram_percent=data.ram_percent,
            energy_kwh=energy["energy_kwh"],
            co2_kg=energy["co2_kg"],
            cost_usd=energy["cost_usd"],
        )
        self.db.add(metric)
        self.db.commit()

        # Invalidate cache
        cache.delete(f"overview_stats")
        cache.delete(f"machine:{machine.id}")

    def get_machine_by_api_key(self, api_key: str) -> Optional[Machine]:
        return self.db.execute(
            select(Machine).where(Machine.api_key == api_key, Machine.is_active == True)
        ).scalar_one_or_none()

    def get_machine(self, machine_id: uuid.UUID) -> Optional[Machine]:
        cached = cache.get(f"machine:{machine_id}")
        if cached:
            return self.db.get(Machine, machine_id)

        machine = self.db.get(Machine, machine_id)
        return machine

    def list_machines(
        self,
        pagination: PaginationParams,
        status_filter: Optional[str] = None,
        search: Optional[str] = None,
    ) -> tuple[list[Machine], int]:
        query = select(Machine).where(Machine.is_active == True)

        if status_filter:
            query = query.where(Machine.status == status_filter)

        if search:
            search_term = f"%{search}%"
            query = query.where(
                Machine.hostname.ilike(search_term)
                | Machine.ip_address.ilike(search_term)
                | Machine.mac_address.ilike(search_term)
            )

        count_query = select(func.count()).select_from(query.subquery())
        total = self.db.execute(count_query).scalar()

        machines = self.db.execute(
            query.order_by(desc(Machine.last_seen))
            .offset(pagination.offset)
            .limit(pagination.limit)
        ).scalars().all()

        return list(machines), total

    def get_machine_history(
        self, machine_id: uuid.UUID, hours: int = 24
    ) -> list[EnergyMetric]:
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        return self.db.execute(
            select(EnergyMetric)
            .where(
                EnergyMetric.machine_id == machine_id,
                EnergyMetric.recorded_at >= cutoff,
            )
            .order_by(EnergyMetric.recorded_at)
        ).scalars().all()

    def mark_offline_machines(self) -> int:
        """Mark machines with no heartbeat in 5 minutes as offline."""
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
        machines = self.db.execute(
            select(Machine).where(
                Machine.last_seen < cutoff,
                Machine.status.in_(["active", "idle"]),
            )
        ).scalars().all()

        for m in machines:
            m.status = "offline"
        self.db.commit()
        return len(machines)
