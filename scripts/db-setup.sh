#!/bin/sh
# =============================================================================
# GreenOps — scripts/db-setup.sh
#
# Runs on EVERY docker compose up via the db-setup one-shot service.
#
# PURPOSE
# ────────
# Ensures the app database user (APP_USER) exists and has the correct password
# from the current .env (APP_PASSWORD). This fixes the root cause of:
#
#   "password authentication failed for user greenops"
#
# PostgreSQL's docker-entrypoint-initdb.d scripts only run once (when the data
# directory is empty). If POSTGRES_PASSWORD changes between deployments, or if
# the container was started previously with different credentials, PostgreSQL
# still has the OLD password. This script uses the stable postgres superuser
# to update the app user's password on every startup — no down -v required.
#
# REQUIRED ENVIRONMENT VARIABLES (set in docker-compose.yml db-setup service)
# ─────────────────────────────────────────────────────────────────────────────
#   PGPASSWORD   — postgres superuser password (POSTGRES_SUPERUSER_PASSWORD)
#   APP_USER     — app database username      (POSTGRES_USER, default: greenops)
#   APP_PASSWORD — app database password      (POSTGRES_PASSWORD)
#   APP_DB       — database name              (POSTGRES_DB,   default: greenops)
#
# PASSWORD SAFETY NOTE
# ─────────────────────
# Single quotes (') in APP_PASSWORD or PGPASSWORD will break SQL string literals.
# Passwords generated with `secrets.token_urlsafe()` never contain single quotes.
# See .env.example for generation commands.
# =============================================================================

set -e

APP_USER="${APP_USER:-greenops}"
APP_DB="${APP_DB:-greenops}"

# ── Input validation ─────────────────────────────────────────────────────────
if [ -z "${APP_PASSWORD}" ]; then
    echo "[db-setup] FATAL: APP_PASSWORD is not set. Check .env and docker-compose.yml." >&2
    exit 1
fi

if [ -z "${PGPASSWORD}" ]; then
    echo "[db-setup] FATAL: PGPASSWORD (superuser password) is not set." >&2
    exit 1
fi

# ── Escape single quotes in values used in SQL string literals ───────────────
# SQL single-quote escape: ' → ''
APP_PASSWORD_SQL=$(printf '%s' "${APP_PASSWORD}" | sed "s/'/''/g")
APP_USER_SQL=$(printf '%s' "${APP_USER}" | sed "s/'/''/g")
APP_DB_SQL=$(printf '%s' "${APP_DB}" | sed "s/'/''/g")

echo "[db-setup] ─────────────────────────────────────────────────────────────"
echo "[db-setup] Syncing credentials for app user '${APP_USER}' on '${APP_DB}'..."
echo "[db-setup] Connecting to PostgreSQL as superuser 'postgres'..."

# ── Step 1: Create or update the app user, grant database ownership ──────────
psql -h db -U postgres -v ON_ERROR_STOP=1 <<SQL
-- Create app user if it doesn't exist, otherwise update its password.
-- Uses PostgreSQL EXECUTE + format() for safe identifier/literal quoting.
DO \$\$
DECLARE
  v_exists BOOLEAN;
BEGIN
  SELECT EXISTS (
    SELECT FROM pg_catalog.pg_roles WHERE rolname = '${APP_USER_SQL}'
  ) INTO v_exists;

  IF NOT v_exists THEN
    EXECUTE format(
      'CREATE ROLE %I WITH LOGIN PASSWORD %L',
      '${APP_USER_SQL}',
      '${APP_PASSWORD_SQL}'
    );
    RAISE NOTICE '[db-setup] Created app user: ${APP_USER_SQL}';
  ELSE
    EXECUTE format(
      'ALTER ROLE %I WITH LOGIN PASSWORD %L',
      '${APP_USER_SQL}',
      '${APP_PASSWORD_SQL}'
    );
    RAISE NOTICE '[db-setup] Updated password for: ${APP_USER_SQL}';
  END IF;
END
\$\$;

-- Ensure the app user owns the database so it can CREATE SCHEMA, run migrations, etc.
GRANT ALL PRIVILEGES ON DATABASE "${APP_DB_SQL}" TO "${APP_USER_SQL}";
ALTER DATABASE "${APP_DB_SQL}" OWNER TO "${APP_USER_SQL}";
SQL

echo "[db-setup] User and database ownership configured."

# ── Step 2: Grant schema-level permissions ───────────────────────────────────
# Must be done in a separate connection to the TARGET database (not postgres).
psql -h db -U postgres -d "${APP_DB}" -v ON_ERROR_STOP=1 <<SQL
-- Grant full access to the public schema for the app user.
-- ALTER DEFAULT PRIVILEGES ensures future tables/sequences are also accessible.
GRANT ALL ON SCHEMA public TO "${APP_USER_SQL}";
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "${APP_USER_SQL}";
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO "${APP_USER_SQL}";
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON TABLES TO "${APP_USER_SQL}";
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON SEQUENCES TO "${APP_USER_SQL}";
SQL

echo "[db-setup] Schema permissions granted."
echo "[db-setup] ─────────────────────────────────────────────────────────────"
echo "[db-setup] App user '${APP_USER}' is configured. Server can now start."
