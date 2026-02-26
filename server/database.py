"""
GreenOps Database Layer
========================
SQLAlchemy async engine, session factory, ORM models, and schema init.

Key fix vs original
-------------------
The original `create_tables()` used:

    DO $$ BEGIN
        CREATE TYPE machine_status AS ENUM (...);
    EXCEPTION WHEN duplicate_object THEN null;
    END $$;

When 4 Gunicorn workers all call create_tables() at the same millisecond on
first boot, they all attempt CREATE TYPE simultaneously.  The duplicate key
hits pg_type's storage-level unique index BEFORE PL/pgSQL's EXCEPTION handler
fires → one worker crashes with IntegrityError → Gunicorn kills all workers.

Fixed by checking existence first:

    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'machine_status') THEN
            CREATE TYPE machine_status AS ENUM (...);
        END IF;
    END $$;

Workers that lose the race simply skip the CREATE instead of raising an error.
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

# ---------------------------------------------------------------------------
# Engine & session factory
# ---------------------------------------------------------------------------

settings = get_settings()

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
# Schema initialisation — called once per worker at startup
# ---------------------------------------------------------------------------

async def create_tables() -> None:
    """
    Create enum types and tables if they don't already exist.

    Multi-worker safety
    -------------------
    Uses IF NOT EXISTS guards on enum creation so that concurrent workers
    racing to call this function on first boot don't cause each other to
    crash with IntegrityError on pg_type's unique index.

    The EXCEPTION WHEN duplicate_object pattern is NOT used here because
    asyncpg raises the error at the storage level before PL/pgSQL's
    exception handler fires, causing spurious worker crashes.
    """
    async with engine.begin() as conn:
        # ── Enum: machine_status ───────────────────────────────────────────
        # Check existence before attempting CREATE to avoid concurrent-worker
        # race on pg_type's unique index.
        await conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_type WHERE typname = 'machine_status'
                ) THEN
                    CREATE TYPE machine_status AS ENUM ('online', 'idle', 'offline');
                END IF;
            END $$;
        """))

        # ── Enum: user_role ───────────────────────────────────────────────
        await conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_type WHERE typname = 'user_role'
                ) THEN
                    CREATE TYPE user_role AS ENUM ('admin', 'viewer');
                END IF;
            END $$;
        """))

        # ── Tables ────────────────────────────────────────────────────────
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id                    SERIAL PRIMARY KEY,
                username              VARCHAR(64) UNIQUE NOT NULL,
                password_hash         VARCHAR(256) NOT NULL,
                role                  user_role NOT NULL DEFAULT 'admin',
                is_active             BOOLEAN NOT NULL DEFAULT true,
                failed_login_attempts INTEGER NOT NULL DEFAULT 0,
                locked_until          TIMESTAMPTZ,
                last_login            TIMESTAMPTZ,
                created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """))

        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_users_username ON users(username);
        """))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id         SERIAL PRIMARY KEY,
                user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_hash VARCHAR(256) UNIQUE NOT NULL,
                issued_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                expires_at TIMESTAMPTZ NOT NULL,
                revoked    BOOLEAN NOT NULL DEFAULT false,
                revoked_at TIMESTAMPTZ,
                user_agent VARCHAR(256),
                ip_address VARCHAR(64)
            );
        """))

        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_refresh_tokens_user_id
                ON refresh_tokens(user_id);
        """))

        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_refresh_tokens_token_hash
                ON refresh_tokens(token_hash);
        """))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS machines (
                id                   SERIAL PRIMARY KEY,
                mac_address          VARCHAR(17) UNIQUE NOT NULL,
                hostname             VARCHAR(255) NOT NULL,
                os_type              VARCHAR(64) NOT NULL,
                os_version           VARCHAR(128),
                ip_address           VARCHAR(64),
                status               machine_status NOT NULL DEFAULT 'offline',
                first_seen           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                last_seen            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                total_idle_seconds   BIGINT NOT NULL DEFAULT 0,
                total_active_seconds BIGINT NOT NULL DEFAULT 0,
                energy_wasted_kwh    DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                energy_cost_usd      DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                agent_version        VARCHAR(32),
                notes                TEXT
            );
        """))

        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_machines_mac_address
                ON machines(mac_address);
        """))

        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_machines_status
                ON machines(status);
        """))

        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_machines_status_last_seen
                ON machines(status, last_seen);
        """))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS heartbeats (
                id               BIGSERIAL PRIMARY KEY,
                machine_id       INTEGER NOT NULL REFERENCES machines(id) ON DELETE CASCADE,
                timestamp        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                idle_seconds     INTEGER NOT NULL DEFAULT 0,
                cpu_usage        DOUBLE PRECISION,
                memory_usage     DOUBLE PRECISION,
                is_idle          BOOLEAN NOT NULL DEFAULT false,
                energy_delta_kwh DOUBLE PRECISION NOT NULL DEFAULT 0.0
            );
        """))

        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_heartbeats_machine_id_timestamp
                ON heartbeats(machine_id, timestamp DESC);
        """))

        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_heartbeats_timestamp
                ON heartbeats(timestamp DESC);
        """))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS agent_tokens (
                id         SERIAL PRIMARY KEY,
                machine_id INTEGER NOT NULL UNIQUE REFERENCES machines(id) ON DELETE CASCADE,
                token_hash VARCHAR(256) UNIQUE NOT NULL,
                issued_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                last_used  TIMESTAMPTZ,
                revoked    BOOLEAN NOT NULL DEFAULT false
            );
        """))

        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_agent_tokens_machine_id
                ON agent_tokens(machine_id);
        """))

        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_agent_tokens_token_hash
                ON agent_tokens(token_hash);
        """))

        # ── updated_at trigger ────────────────────────────────────────────
        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION update_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = NOW();
                RETURN NEW;
            END;
            $$ LANGUAGE 'plpgsql';
        """))

        await conn.execute(text("""
            DROP TRIGGER IF EXISTS update_users_updated_at ON users;
        """))

        await conn.execute(text("""
            CREATE TRIGGER update_users_updated_at
                BEFORE UPDATE ON users
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();
        """))

    logger.info("database_schema_ready")
