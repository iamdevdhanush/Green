"""Machine / Device model"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MachineStatus(str):
    ACTIVE = "active"
    IDLE = "idle"
    OFFLINE = "offline"
    SHUTDOWN = "shutdown"


class Machine(Base):
    __tablename__ = "machines"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Device fingerprint
    mac_address: Mapped[str] = mapped_column(String(17), unique=True, index=True, nullable=False)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    os_version: Mapped[str] = mapped_column(String(255), nullable=True)
    cpu_info: Mapped[str] = mapped_column(String(255), nullable=True)
    ram_gb: Mapped[float] = mapped_column(Float, nullable=True)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)

    # Auth
    api_key: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    # Status
    status: Mapped[str] = mapped_column(String(20), default="offline", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Telemetry
    idle_minutes: Mapped[int] = mapped_column(Integer, default=0)
    total_idle_hours: Mapped[float] = mapped_column(Float, default=0.0)
    total_energy_kwh: Mapped[float] = mapped_column(Float, default=0.0)
    total_co2_kg: Mapped[float] = mapped_column(Float, default=0.0)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)

    # Timestamps
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    energy_metrics = relationship("EnergyMetric", back_populates="machine", cascade="all, delete-orphan")
    shutdown_commands = relationship("ShutdownCommand", back_populates="machine", cascade="all, delete-orphan")
    monthly_analytics = relationship("MonthlyAnalytics", back_populates="machine", cascade="all, delete-orphan")
