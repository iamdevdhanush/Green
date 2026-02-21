"""Energy Metric model - per-heartbeat telemetry records"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class EnergyMetric(Base):
    __tablename__ = "energy_metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    machine_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    # Snapshot at this moment
    idle_minutes: Mapped[int] = mapped_column(Integer, default=0)
    cpu_percent: Mapped[float] = mapped_column(Float, default=0.0)
    ram_percent: Mapped[float] = mapped_column(Float, default=0.0)

    # Calculated energy for this interval
    energy_kwh: Mapped[float] = mapped_column(Float, default=0.0)
    co2_kg: Mapped[float] = mapped_column(Float, default=0.0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    machine = relationship("Machine", back_populates="energy_metrics")
