"""Monthly Analytics pre-aggregation model"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MonthlyAnalytics(Base):
    __tablename__ = "monthly_analytics"
    __table_args__ = (
        UniqueConstraint("machine_id", "year", "month", name="uq_machine_month"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    machine_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    # machine_id=None means org-level aggregate
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    total_kwh: Mapped[float] = mapped_column(Float, default=0.0)
    total_co2_kg: Mapped[float] = mapped_column(Float, default=0.0)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    total_idle_hours: Mapped[float] = mapped_column(Float, default=0.0)

    # Comparison vs previous month
    kwh_change_pct: Mapped[float] = mapped_column(Float, nullable=True)
    co2_change_pct: Mapped[float] = mapped_column(Float, nullable=True)
    cost_change_pct: Mapped[float] = mapped_column(Float, nullable=True)

    aggregated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    machine = relationship("Machine", back_populates="monthly_analytics")
