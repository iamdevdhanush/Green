"""Shutdown Command model"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CommandStatus(str):
    PENDING = "pending"
    EXECUTED = "executed"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ShutdownCommand(Base):
    __tablename__ = "shutdown_commands"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    machine_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    issued_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    idle_threshold_minutes: Mapped[int] = mapped_column(Integer, default=15)
    rejection_reason: Mapped[str] = mapped_column(Text, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)

    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    machine = relationship("Machine", back_populates="shutdown_commands")
