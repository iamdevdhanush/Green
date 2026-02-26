#!/bin/bash
# =============================================================================
# GreenOps — scripts/reset-db-password.sh
#
# Resets the greenops PostgreSQL role password to match the current
# POSTGRES_PASSWORD in .env — WITHOUT wiping the data volume.
#
# How it works:
#   1. Temporarily patches pg_hba.conf to use "trust" auth (no password needed)
#   2. Reloads PostgreSQL config
#   3. Connects without a password and runs ALTER ROLE ... PASSWORD '...'
#   4. Restores pg_hba.conf to scram-sha-256
#   5. Reloads again
#
# Usage:
#   chmod +x scripts/reset-db-password.sh
#   bash scripts/reset-db-password.sh
#
# Requirements:
#   - greenops-db container must be running
#   - .env must exist with POSTGRES_PASSWORD and POSTGRES_USER set
# =============================================================================
set -e

# ── Load .env ────────────────────────────────────────────────────────────────
if [ ! -f .env ]; then
    echo "ERROR: .env file not found. Run: cp .env.example .env" >&2
    exit 1
fi

# Source only the variables we need (safe subset)
POSTGRES_USER=$(grep '^POSTGRES_USER=' .env | cut -d= -f2- | tr -d '"' | tr -d "'")
POSTGRES_PASSWORD=$(grep '^POSTGRES_PASSWORD=' .env | cut -d= -f2- | tr -d '"' | tr -d "'")
POSTGRES_DB=$(grep '^POSTGRES_DB=' .env | cut -d= -f2- | tr -d '"' | tr -d "'")

POSTGRES_USER="${POSTGRES_USER:-greenops}"
POSTGRES_DB="${POSTGRES_DB:-greenops}"

if [ -z "$POSTGRES_PASSWORD" ]; then
    echo "ERROR: POSTGRES_PASSWORD is not set in .env" >&2
    exit 1
fi

DB_CONTAINER="greenops-db"

echo "──────────────────────────────────────────────────────────"
echo " GreenOps — PostgreSQL password reset"
echo " Container : $DB_CONTAINER"
echo " User      : $POSTGRES_USER"
echo " Database  : $POSTGRES_DB"
echo "──────────────────────────────────────────────────────────"

# ── Check container is running ───────────────────────────────────────────────
if ! docker ps --format '{{.Names}}' | grep -q "^${DB_CONTAINER}$"; then
    echo "ERROR: Container '${DB_CONTAINER}' is not running."
    echo "Start it with: docker compose up -d db"
    exit 1
fi

# ── Step 1: Patch pg_hba.conf to trust (no password required) ────────────────
echo "[1/5] Patching pg_hba.conf to use trust authentication..."
docker exec "$DB_CONTAINER" sh -c "
    cp /var/lib/postgresql/data/pg_hba.conf /var/lib/postgresql/data/pg_hba.conf.bak
    sed -i 's/scram-sha-256/trust/g' /var/lib/postgresql/data/pg_hba.conf
"

# ── Step 2: Reload PostgreSQL to apply trust auth ────────────────────────────
echo "[2/5] Reloading PostgreSQL config..."
docker exec "$DB_CONTAINER" su -s /bin/sh postgres -c \
    "pg_ctl reload -D /var/lib/postgresql/data" 2>/dev/null || \
docker exec "$DB_CONTAINER" sh -c \
    "kill -HUP \$(head -1 /var/lib/postgresql/data/postmaster.pid)"

sleep 2  # Give postgres a moment to reload

# ── Step 3: Reset the password ───────────────────────────────────────────────
# SQL-escape single quotes in the password
ESCAPED_PASSWORD=$(printf '%s' "$POSTGRES_PASSWORD" | sed "s/'/''/g")

echo "[3/5] Resetting password for role '${POSTGRES_USER}'..."
docker exec "$DB_CONTAINER" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    -c "ALTER ROLE \"${POSTGRES_USER}\" WITH PASSWORD '${ESCAPED_PASSWORD}';"

# ── Step 4: Restore pg_hba.conf to scram-sha-256 ─────────────────────────────
echo "[4/5] Restoring pg_hba.conf to scram-sha-256..."
docker exec "$DB_CONTAINER" sh -c "
    cp /var/lib/postgresql/data/pg_hba.conf.bak /var/lib/postgresql/data/pg_hba.conf
    rm /var/lib/postgresql/data/pg_hba.conf.bak
"

# ── Step 5: Reload PostgreSQL to enforce scram auth again ────────────────────
echo "[5/5] Reloading PostgreSQL config..."
docker exec "$DB_CONTAINER" sh -c \
    "kill -HUP \$(head -1 /var/lib/postgresql/data/postmaster.pid)"

sleep 2

# ── Verify the new password works ────────────────────────────────────────────
echo ""
echo "Verifying new password..."
if docker exec "$DB_CONTAINER" sh -c \
    "PGPASSWORD='${POSTGRES_PASSWORD}' psql -U '${POSTGRES_USER}' -d '${POSTGRES_DB}' -c 'SELECT 1' -q" \
    > /dev/null 2>&1; then
    echo "──────────────────────────────────────────────────────────"
    echo " Password reset successful!"
    echo " Now run: docker compose up"
    echo "──────────────────────────────────────────────────────────"
else
    echo "──────────────────────────────────────────────────────────"
    echo " ERROR: Verification failed. Check the logs above."
    echo " If this keeps failing, wipe the volume:"
    echo "   docker compose down -v && docker compose up --build"
    echo "──────────────────────────────────────────────────────────"
    exit 1
fi
