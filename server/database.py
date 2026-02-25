"""
GreenOps Database - Async SQLAlchemy with PostgreSQL
"""
import enum
from datetime import datetime
from typing import AsyncGenerator

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, relationship

from config import get_settings

settings = get_settings()

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


class MachineStatus(str, enum.Enum):
    ONLINE = "online"
    IDLE = "idle"
    OFFLINE = "offline"


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    VIEWER = "viewer"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.ADMIN, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    last_login = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("NOW()"), onupdate=datetime.utcnow, nullable=False)

    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(256), unique=True, nullable=False, index=True)
    issued_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    user_agent = Column(String(256), nullable=True)
    ip_address = Column(String(64), nullable=True)

    user = relationship("User", back_populates="refresh_tokens")


class Machine(Base):
    __tablename__ = "machines"

    id = Column(Integer, primary_key=True, index=True)
    mac_address = Column(String(17), unique=True, nullable=False, index=True)
    hostname = Column(String(255), nullable=False)
    os_type = Column(String(64), nullable=False)
    os_version = Column(String(128), nullable=True)
    ip_address = Column(String(64), nullable=True)
    status = Column(Enum(MachineStatus), default=MachineStatus.OFFLINE, nullable=False, index=True)
    first_seen = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    last_seen = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    total_idle_seconds = Column(BigInteger, default=0, nullable=False)
    total_active_seconds = Column(BigInteger, default=0, nullable=False)
    energy_wasted_kwh = Column(Float, default=0.0, nullable=False)
    energy_cost_usd = Column(Float, default=0.0, nullable=False)
    agent_version = Column(String(32), nullable=True)
    notes = Column(Text, nullable=True)

    heartbeats = relationship("Heartbeat", back_populates="machine", cascade="all, delete-orphan")
    agent_token = relationship("AgentToken", back_populates="machine", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_machines_status_last_seen", "status", "last_seen"),
    )


class Heartbeat(Base):
    __tablename__ = "heartbeats"

    id = Column(BigInteger, primary_key=True, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    idle_seconds = Column(Integer, default=0, nullable=False)
    cpu_usage = Column(Float, nullable=True)
    memory_usage = Column(Float, nullable=True)
    is_idle = Column(Boolean, default=False, nullable=False)
    energy_delta_kwh = Column(Float, default=0.0, nullable=False)

    machine = relationship("Machine", back_populates="heartbeats")

    __table_args__ = (
        Index("ix_heartbeats_machine_id_timestamp", "machine_id", "timestamp"),
        Index("ix_heartbeats_timestamp", "timestamp"),
    )


class AgentToken(Base):
    __tablename__ = "agent_tokens"

    id = Column(Integer, primary_key=True, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    token_hash = Column(String(256), unique=True, nullable=False)
    issued_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    last_used = Column(DateTime(timezone=True), nullable=True)
    revoked = Column(Boolean, default=False, nullable=False)

    machine = relationship("Machine", back_populates="agent_token")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables():
    """Create all tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
