"""
GreenOps Database Layer
=======================
Async SQLAlchemy with PostgreSQL 16.

Enum handling:
  UserRole and MachineStatus both inherit from (str, enum.Enum).
  This means:
    - UserRole.ADMIN == "admin" is True (str comparison works)
    - JSON serialization produces "admin", not "<UserRole.ADMIN: 'admin'>"
    - values_callable in the Enum column type ensures SQLAlchemy sends
      "admin" (the value) to PostgreSQL, not "ADMIN" (the name).

  Without values_callable, SQLAlchemy sends the enum NAME ("ADMIN") to
  PostgreSQL, which rejects it because the PG enum type was created with
  lowercase values ('admin', 'viewer'). This was the source of:
    "invalid input value for enum user_role: 'ADMIN'"
"""

import enum
from datetime import datetime
from typing import AsyncGenerator

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Enum,
    Float, ForeignKey, Index, Integer, String, Text, text,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession, async_sessionmaker, create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship

from config import get_settings

settings = get_settings()

# ── Engine ────────────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,          # log all SQL in DEBUG mode
    pool_size=10,                 # connections per worker
    max_overflow=20,              # burst connections above pool_size
    pool_timeout=30,              # wait this long for a connection before raising
    pool_recycle=1800,            # recycle connections older than 30 min
    pool_pre_ping=True,           # check connections are alive before using
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,       # don't lazy-load after commit in async context
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


# ── Enums ─────────────────────────────────────────────────────────────────────

class MachineStatus(str, enum.Enum):
    """
    str subclass: MachineStatus.ONLINE == "online" is True.
    values_callable ensures PostgreSQL receives "online" not "ONLINE".
    """
    ONLINE  = "online"
    IDLE    = "idle"
    OFFLINE = "offline"


class UserRole(str, enum.Enum):
    """
    str subclass: UserRole.ADMIN == "admin" is True.
    values_callable ensures PostgreSQL receives "admin" not "ADMIN".

    _missing_() normalizes case-mismatched strings:
      UserRole("ADMIN") → UserRole.ADMIN  (instead of raising ValueError)
      UserRole("invalid") → raises ValueError with clear message
    """
    ADMIN  = "admin"
    VIEWER = "viewer"

    @classmethod
    def _missing_(cls, value: object):
        """
        Called when UserRole(value) fails the standard lookup.
        Normalizes case so UserRole("ADMIN") → UserRole.ADMIN.
        """
        if isinstance(value, str):
            normalized = value.strip().lower()
            for member in cls:
                if member.value == normalized:
                    return member
        raise ValueError(
            f"'{value}' is not a valid {cls.__name__}. "
            f"Valid values: {[m.value for m in cls]}"
        )


# ── SQLAlchemy column type declarations ───────────────────────────────────────
#
# values_callable=lambda obj: [e.value for e in obj]
#   Forces SQLAlchemy to send enum VALUES ("admin") to PostgreSQL,
#   not enum NAMES ("ADMIN").
#
# create_type=False
#   Tells SQLAlchemy NOT to try to CREATE the enum type — it was already
#   created by the migration SQL (001_initial_schema.sql).

_machine_status_pg = Enum(
    MachineStatus,
    name="machine_status",
    create_type=False,
    values_callable=lambda obj: [e.value for e in obj],
)

_user_role_pg = Enum(
    UserRole,
    name="user_role",
    create_type=False,
    values_callable=lambda obj: [e.value for e in obj],
)


# ── Models ────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id                    = Column(Integer, primary_key=True, index=True)
    username              = Column(String(64), unique=True, nullable=False, index=True)
    password_hash         = Column(String(256), nullable=False)
    role                  = Column(_user_role_pg, default=UserRole.ADMIN, nullable=False)
    is_active             = Column(Boolean, default=True, nullable=False)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until          = Column(DateTime(timezone=True), nullable=True)
    last_login            = Column(DateTime(timezone=True), nullable=True)
    created_at            = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at            = Column(DateTime(timezone=True), server_default=text("NOW()"),
                                   onupdate=datetime.utcnow, nullable=False)

    refresh_tokens = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(256), unique=True, nullable=False, index=True)
    issued_at  = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked    = Column(Boolean, default=False, nullable=False)
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
    status               = Column(_machine_status_pg, default=MachineStatus.OFFLINE,
                                  nullable=False, index=True)
    first_seen           = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    last_seen            = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    total_idle_seconds   = Column(BigInteger, default=0, nullable=False)
    total_active_seconds = Column(BigInteger, default=0, nullable=False)
    energy_wasted_kwh    = Column(Float, default=0.0, nullable=False)
    energy_cost_usd      = Column(Float, default=0.0, nullable=False)
    agent_version        = Column(String(32), nullable=True)
    notes                = Column(Text, nullable=True)

    heartbeats  = relationship("Heartbeat",   back_populates="machine", cascade="all, delete-orphan")
    agent_token = relationship("AgentToken",  back_populates="machine", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_machines_status_last_seen", "status", "last_seen"),
    )


class Heartbeat(Base):
    __tablename__ = "heartbeats"

    id               = Column(BigInteger, primary_key=True, index=True)
    machine_id       = Column(Integer, ForeignKey("machines.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp        = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    idle_seconds     = Column(Integer, default=0, nullable=False)
    cpu_usage        = Column(Float, nullable=True)
    memory_usage     = Column(Float, nullable=True)
    is_idle          = Column(Boolean, default=False, nullable=False)
    energy_delta_kwh = Column(Float, default=0.0, nullable=False)

    machine = relationship("Machine", back_populates="heartbeats")

    __table_args__ = (
        Index("ix_heartbeats_machine_id_timestamp", "machine_id", "timestamp"),
        Index("ix_heartbeats_timestamp", "timestamp"),
    )


class AgentToken(Base):
    __tablename__ = "agent_tokens"

    id         = Column(Integer, primary_key=True, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id", ondelete="CASCADE"),
                        unique=True, nullable=False, index=True)
    token_hash = Column(String(256), unique=True, nullable=False)
    issued_at  = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    last_used  = Column(DateTime(timezone=True), nullable=True)
    revoked    = Column(Boolean, default=False, nullable=False)

    machine = relationship("Machine", back_populates="agent_token")


# ── Session dependency ────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a database session.
    Auto-commits on success, auto-rolls-back on exception.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Table creation ────────────────────────────────────────────────────────────

async def create_tables() -> None:
    """
    Create enum types and tables if they don't exist.
    Safe to call multiple times (idempotent).

    Note: The migration file (migrations/001_initial_schema.sql) also does
    this on first container startup via Docker's initdb.d mechanism. This
    function is a safety net for cases where the container is started without
    the migrations volume, or for testing.
    """
    async with engine.begin() as conn:
        # Create enum types first (tables depend on them)
        await conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE machine_status AS ENUM ('online', 'idle', 'offline');
            EXCEPTION WHEN duplicate_object THEN null;
            END $$;
        """))
        await conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE user_role AS ENUM ('admin', 'viewer');
            EXCEPTION WHEN duplicate_object THEN null;
            END $$;
        """))
        # Create tables (checkfirst=True is equivalent to CREATE TABLE IF NOT EXISTS)
        await conn.run_sync(Base.metadata.create_all, checkfirst=True)
