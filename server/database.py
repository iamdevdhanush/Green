"""
GreenOps Database Layer
========================
SQLAlchemy async engine, session factory, ORM models.

Schema management policy
-------------------------
ALL DDL (CREATE TABLE, CREATE TYPE, CREATE TRIGGER, CREATE FUNCTION) is
managed exclusively by the migration service (migrations/init-scripts/).
The application NEVER runs DDL at runtime.

Rationale:
  - Multiple Gunicorn workers starting simultaneously all call create_tables().
  - DDL statements acquire heavyweight locks on pg_class, pg_type, etc.
  - Even with IF NOT EXISTS guards, concurrent DROP TRIGGER + CREATE TRIGGER
    causes a DeadlockDetectedError on pg's system catalog.
  - The fix: separate concerns. Migrations run once, before the app starts,
    in a dedicated one-shot container. The app only reads/writes data.

create_tables() is kept for backwards compatibility but now only verifies
the schema is present — it does not modify it.
"""

import enum
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Double,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship

from config import get_settings

logger = structlog.get_logger(__name__)

settings = get_settings()

# ---------------------------------------------------------------------------
# Engine & session factory
# ---------------------------------------------------------------------------

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=1800,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ---------------------------------------------------------------------------
# Dependency — yields an AsyncSession per request
# ---------------------------------------------------------------------------

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class MachineStatus(str, enum.Enum):
    ONLINE  = "online"
    IDLE    = "idle"
    OFFLINE = "offline"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            for member in cls:
                if member.value == value.lower():
                    return member
        return None


class UserRole(str, enum.Enum):
    ADMIN  = "admin"
    VIEWER = "viewer"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            for member in cls:
                if member.value == value.lower():
                    return member
        return None


# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id                    = Column(Integer, primary_key=True, index=True)
    username              = Column(String(64), unique=True, nullable=False, index=True)
    password_hash         = Column(String(256), nullable=False)
    role                  = Column(String(32), nullable=False, default="admin")
    is_active             = Column(Boolean, nullable=False, default=True)
    failed_login_attempts = Column(Integer, nullable=False, default=0)
    locked_until          = Column(DateTime(timezone=True), nullable=True)
    last_login            = Column(DateTime(timezone=True), nullable=True)
    created_at            = Column(DateTime(timezone=True), nullable=False,
                                   server_default=text("NOW()"))
    updated_at            = Column(DateTime(timezone=True), nullable=False,
                                   server_default=text("NOW()"))

    refresh_tokens = relationship("RefreshToken", back_populates="user",
                                  cascade="all, delete-orphan")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    token_hash = Column(String(256), unique=True, nullable=False, index=True)
    issued_at  = Column(DateTime(timezone=True), nullable=False,
                        server_default=text("NOW()"))
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked    = Column(Boolean, nullable=False, default=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    user_agent = Column(String(256), nullable=True)
    ip_address = Column(String(64), nullable=True)

    user = relationship("User", back_populates="refresh_tokens")


class Machine(Base):
    __tablename__ = "machines"

    id                   = Column(Integer, primary_key=True, index=True)
    mac_address          = Column(String(17), unique=True, nullable=False, index=True)
    hostname             = Column(String(255), nullable=False)
    os_type              = Column(String(64), nullable=False)
    os_version           = Column(String(128), nullable=True)
    ip_address           = Column(String(64), nullable=True)
    status               = Column(String(32), nullable=False, default="offline")
    first_seen           = Column(DateTime(timezone=True), nullable=False,
                                  server_default=text("NOW()"))
    last_seen            = Column(DateTime(timezone=True), nullable=False,
                                  server_default=text("NOW()"))
    total_idle_seconds   = Column(BigInteger, nullable=False, default=0)
    total_active_seconds = Column(BigInteger, nullable=False, default=0)
    energy_wasted_kwh    = Column(Double, nullable=False, default=0.0)
    energy_cost_usd      = Column(Double, nullable=False, default=0.0)
    agent_version        = Column(String(32), nullable=True)
    notes                = Column(Text, nullable=True)

    heartbeats   = relationship("Heartbeat", back_populates="machine",
                                cascade="all, delete-orphan")
    agent_tokens = relationship("AgentToken", back_populates="machine",
                                cascade="all, delete-orphan", uselist=False)

    __table_args__ = (
        Index("ix_machines_status_last_seen", "status", "last_seen"),
    )


class Heartbeat(Base):
    __tablename__ = "heartbeats"

    id               = Column(BigInteger, primary_key=True, index=True)
    machine_id       = Column(Integer, ForeignKey("machines.id", ondelete="CASCADE"),
                              nullable=False)
    timestamp        = Column(DateTime(timezone=True), nullable=False,
                              server_default=text("NOW()"))
    idle_seconds     = Column(Integer, nullable=False, default=0)
    cpu_usage        = Column(Float, nullable=True)
    memory_usage     = Column(Float, nullable=True)
    is_idle          = Column(Boolean, nullable=False, default=False)
    energy_delta_kwh = Column(Double, nullable=False, default=0.0)

    machine = relationship("Machine", back_populates="heartbeats")

    __table_args__ = (
        Index("ix_heartbeats_machine_id_timestamp", "machine_id", "timestamp"),
        Index("ix_heartbeats_timestamp", "timestamp"),
    )


class AgentToken(Base):
    __tablename__ = "agent_tokens"

    id         = Column(Integer, primary_key=True, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id", ondelete="CASCADE"),
                        nullable=False, unique=True, index=True)
    token_hash = Column(String(256), unique=True, nullable=False, index=True)
    issued_at  = Column(DateTime(timezone=True), nullable=False,
                        server_default=text("NOW()"))
    last_used  = Column(DateTime(timezone=True), nullable=True)
    revoked    = Column(Boolean, nullable=False, default=False)

    machine = relationship("Machine", back_populates="agent_tokens")


# ---------------------------------------------------------------------------
# Schema verification — NOT schema creation
# ---------------------------------------------------------------------------

async def verify_schema() -> None:
    """
    Verify that required tables exist. Raises RuntimeError if the schema
    is not present (migrations have not run).

    This function does NOT create any tables, types, functions, or triggers.
    All DDL is managed by migrations/init-scripts/ which run in the
    dedicated 'migrate' service before the app container starts.

    Why no DDL here:
      Multiple Gunicorn workers call this function concurrently at startup.
      Even IF-NOT-EXISTS DDL acquires heavy locks on pg_class/pg_type, and
      DROP TRIGGER + CREATE TRIGGER in particular causes deadlocks between
      workers competing for the same system catalog entries.
    """
    required_tables = ["users", "machines", "heartbeats", "agent_tokens", "refresh_tokens"]

    async with engine.connect() as conn:
        for table in required_tables:
            result = await conn.execute(
                text(
                    "SELECT EXISTS ("
                    "  SELECT FROM information_schema.tables"
                    "  WHERE table_schema = 'public' AND table_name = :tname"
                    ")"
                ),
                {"tname": table},
            )
            exists = result.scalar()
            if not exists:
                raise RuntimeError(
                    f"Required table '{table}' does not exist. "
                    "Ensure the 'migrate' service completed successfully before "
                    "starting the application. "
                    "Run: docker compose run --rm migrate"
                )

    logger.info("database_schema_verified", tables=required_tables)


# Keep the old name as an alias so existing imports don't break during
# the transition. Both point to the same verification-only function.
create_tables = verify_schema
