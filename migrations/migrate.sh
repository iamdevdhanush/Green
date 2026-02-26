#!/bin/sh
# =============================================================================
# GreenOps — migrations/migrate.sh
#
# One-shot migration runner. Runs inside the 'migrate' Docker service.
# Executes all SQL migration files in alphabetical order.
#
# Design:
#   - Uses a schema_migrations table to track which migrations have run.
#   - Each migration is applied exactly once (idempotent across restarts).
#   - Runs before the app starts (enforced by depends_on in docker-compose.yml).
#   - Exits 0 on success, non-zero on failure (halts app startup).
#
# This eliminates ALL DDL from the application runtime, preventing:
#   - Worker deadlocks on pg system catalog locks
#   - Race conditions between concurrent Gunicorn workers
#   - CREATE/DROP conflicts on triggers, functions, and enum types
#
# Usage:
#   Runs automatically via docker compose as the 'migrate' service.
#   Manual run: docker compose run --rm migrate
# =============================================================================
set -e

# ── Environment ───────────────────────────────────────────────────────────────
DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${POSTGRES_USER:-greenops}"
DB_PASS="${POSTGRES_PASSWORD}"
DB_NAME="${POSTGRES_DB:-greenops}"
MIGRATIONS_DIR="${MIGRATIONS_DIR:-/migrations}"

if [ -z "$DB_PASS" ]; then
    echo "[migrate] FATAL: POSTGRES_PASSWORD is not set." >&2
    exit 1
fi

export PGPASSWORD="$DB_PASS"

# ── Wait for PostgreSQL ───────────────────────────────────────────────────────
echo "[migrate] Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT}..."
attempt=0
max_attempts=30
until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -q; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge "$max_attempts" ]; then
        echo "[migrate] FATAL: PostgreSQL did not become ready after ${max_attempts} attempts." >&2
        exit 1
    fi
    echo "[migrate] Attempt ${attempt}/${max_attempts}: PostgreSQL not ready. Waiting 2s..."
    sleep 2
done
echo "[migrate] PostgreSQL is ready."

# ── Bootstrap schema_migrations table ────────────────────────────────────────
# This table tracks applied migrations. Created once, idempotent.
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 <<'SQL'
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     VARCHAR(255) PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
SQL

echo "[migrate] schema_migrations table ready."

# ── Apply migrations in order ─────────────────────────────────────────────────
migration_count=0
applied_count=0

for migration_file in $(ls -1 "${MIGRATIONS_DIR}"/*.sql 2>/dev/null | sort); do
    version=$(basename "$migration_file")
    migration_count=$((migration_count + 1))

    # Check if already applied
    already_applied=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
        -tAc "SELECT COUNT(*) FROM schema_migrations WHERE version = '${version}'")

    if [ "$already_applied" = "1" ]; then
        echo "[migrate] [SKIP]  ${version} (already applied)"
        continue
    fi

    echo "[migrate] [APPLY] ${version}..."

    # Run migration inside a transaction. If it fails, the transaction rolls
    # back and the version is NOT recorded — safe to retry.
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
        -v ON_ERROR_STOP=1 \
        --single-transaction \
        -f "$migration_file"

    # Record successful migration
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
        -v ON_ERROR_STOP=1 \
        -c "INSERT INTO schema_migrations (version) VALUES ('${version}');"

    applied_count=$((applied_count + 1))
    echo "[migrate] [DONE]  ${version}"
done

echo "[migrate] ─────────────────────────────────────────────────────────────"
echo "[migrate] Migration complete: ${applied_count} applied, $((migration_count - applied_count)) skipped."
echo "[migrate] ─────────────────────────────────────────────────────────────"
