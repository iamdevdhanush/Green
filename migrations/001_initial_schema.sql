-- GreenOps Initial Schema Migration
-- Applied automatically via Docker Compose on first start
-- For manual apply: psql $DATABASE_URL < migrations/001_initial_schema.sql

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enums
DO $$ BEGIN
    CREATE TYPE machine_status AS ENUM ('online', 'idle', 'offline');
EXCEPTION WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('admin', 'viewer');
EXCEPTION WHEN duplicate_object THEN null;
END $$;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(64) UNIQUE NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    role user_role NOT NULL DEFAULT 'admin',
    is_active BOOLEAN NOT NULL DEFAULT true,
    failed_login_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TIMESTAMPTZ,
    last_login TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_users_username ON users(username);

-- Refresh tokens table
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(256) UNIQUE NOT NULL,
    issued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked BOOLEAN NOT NULL DEFAULT false,
    revoked_at TIMESTAMPTZ,
    user_agent VARCHAR(256),
    ip_address VARCHAR(64)
);
CREATE INDEX IF NOT EXISTS ix_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS ix_refresh_tokens_token_hash ON refresh_tokens(token_hash);

-- Machines table
CREATE TABLE IF NOT EXISTS machines (
    id SERIAL PRIMARY KEY,
    mac_address VARCHAR(17) UNIQUE NOT NULL,
    hostname VARCHAR(255) NOT NULL,
    os_type VARCHAR(64) NOT NULL,
    os_version VARCHAR(128),
    ip_address VARCHAR(64),
    status machine_status NOT NULL DEFAULT 'offline',
    first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    total_idle_seconds BIGINT NOT NULL DEFAULT 0,
    total_active_seconds BIGINT NOT NULL DEFAULT 0,
    energy_wasted_kwh DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    energy_cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    agent_version VARCHAR(32),
    notes TEXT
);
CREATE INDEX IF NOT EXISTS ix_machines_mac_address ON machines(mac_address);
CREATE INDEX IF NOT EXISTS ix_machines_status ON machines(status);
CREATE INDEX IF NOT EXISTS ix_machines_status_last_seen ON machines(status, last_seen);

-- Heartbeats table
CREATE TABLE IF NOT EXISTS heartbeats (
    id BIGSERIAL PRIMARY KEY,
    machine_id INTEGER NOT NULL REFERENCES machines(id) ON DELETE CASCADE,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    idle_seconds INTEGER NOT NULL DEFAULT 0,
    cpu_usage DOUBLE PRECISION,
    memory_usage DOUBLE PRECISION,
    is_idle BOOLEAN NOT NULL DEFAULT false,
    energy_delta_kwh DOUBLE PRECISION NOT NULL DEFAULT 0.0
);
CREATE INDEX IF NOT EXISTS ix_heartbeats_machine_id_timestamp ON heartbeats(machine_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS ix_heartbeats_timestamp ON heartbeats(timestamp DESC);

-- Agent tokens table
CREATE TABLE IF NOT EXISTS agent_tokens (
    id SERIAL PRIMARY KEY,
    machine_id INTEGER NOT NULL UNIQUE REFERENCES machines(id) ON DELETE CASCADE,
    token_hash VARCHAR(256) UNIQUE NOT NULL,
    issued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used TIMESTAMPTZ,
    revoked BOOLEAN NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS ix_agent_tokens_machine_id ON agent_tokens(machine_id);
CREATE INDEX IF NOT EXISTS ix_agent_tokens_token_hash ON agent_tokens(token_hash);

-- Updated at trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Cleanup old heartbeats (run periodically via cron or pg_cron)
-- DELETE FROM heartbeats WHERE timestamp < NOW() - INTERVAL '90 days';
