"""
GreenOps Server — Production-ready FastAPI application

Startup sequence (lifespan):
  1. Validate required environment variables (fail fast on config errors)
  2. Wait for PostgreSQL with exponential backoff (survive transient DB delays)
  3. Create tables / verify schema
  4. Bootstrap admin user (idempotent, multi-worker-safe via pg_advisory_xact_lock)
  5. Yield (application serves requests)
  6. Shutdown: dispose engine, flush logs
"""
import asyncio
import logging
import os
import sys
import time
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from config import get_settings
from database import create_tables, engine
from middleware.rate_limiter import RateLimitMiddleware
from middleware.request_id import RequestIDMiddleware
from middleware.security_headers import SecurityHeadersMiddleware
from routers import auth, agents, machines, dashboard

# ── Structured logging setup ─────────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
        if os.getenv("ENV", "development") == "production"
        else structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


# ── DB connection retry ───────────────────────────────────────────────────────

async def _wait_for_database(
    max_attempts: int = 10,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
) -> bool:
    """
    Wait for PostgreSQL to accept connections, with exponential backoff.

    Returns True if the connection succeeded within max_attempts.
    Returns False if all attempts are exhausted (caller should sys.exit).

    This replaces the previous behaviour of crashing immediately on any DB error.
    Transient failures (DB still starting, brief network blip, container restart
    race) are retried gracefully. Only true connection exhaustion is fatal.

    Backoff schedule (base_delay=2, max_delay=60):
      Attempt 1: immediate
      Attempt 2: 2s
      Attempt 3: 4s
      Attempt 4: 8s
      Attempt 5: 16s
      Attempt 6: 32s
      Attempt 7+: 60s (capped)
    """
    from sqlalchemy import text as sql_text

    for attempt in range(1, max_attempts + 1):
        try:
            async with engine.connect() as conn:
                await conn.execute(sql_text("SELECT 1"))
            logger.info("database_connected", attempt=attempt)
            return True

        except Exception as exc:
            if attempt >= max_attempts:
                logger.error(
                    "database_connection_exhausted",
                    attempts=max_attempts,
                    error=str(exc),
                    hint=(
                        "Check that POSTGRES_PASSWORD in .env matches the credentials "
                        "used when the postgres_data volume was first created. "
                        "If you changed the password, run 'docker compose up' again — "
                        "the db-setup service will sync the credentials automatically."
                    ),
                )
                return False

            # Exponential backoff capped at max_delay
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            logger.warning(
                "database_not_ready",
                attempt=attempt,
                max_attempts=max_attempts,
                retry_in_seconds=round(delay, 1),
                error=str(exc),
            )
            await asyncio.sleep(delay)

    return False  # Should be unreachable, but satisfies the type checker.


# ── ASGI lifespan ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    ASGI lifespan handler. Runs startup logic before the first request
    and cleanup logic after the last.

    Gunicorn multi-worker note
    ─────────────────────────
    With preload_app=True (see gunicorn.conf.py), the master process runs this
    lifespan ONCE. Workers are forked after startup completes and inherit the
    already-initialized state. ensure_admin_exists() is called exactly once.
    """
    settings = get_settings()
    logger.info("greenops_starting", version="2.0.0", environment=settings.ENV)

    # ── 1. Validate configuration ─────────────────────────────────────────
    # sys.exit here is intentional: config errors are not transient.
    # A misconfigured server is worse than a server that won't start.
    missing = settings.validate()
    if missing:
        for issue in missing:
            logger.error("config_validation_failed", issue=issue)
        logger.error(
            "startup_aborted",
            reason="Fix the configuration issues above, then restart.",
        )
        sys.exit(1)

    # ── 2. Wait for database (retry with backoff) ─────────────────────────
    # Does NOT sys.exit immediately — gives PostgreSQL time to finish starting.
    # The db-setup service in docker-compose runs before the server starts,
    # but asyncpg connections may still briefly fail during Gunicorn worker spawn.
    db_ready = await _wait_for_database(max_attempts=10, base_delay=2.0)
    if not db_ready:
        logger.error(
            "startup_aborted",
            reason=(
                "Could not connect to PostgreSQL after 10 attempts. "
                "Verify DATABASE_URL, POSTGRES_PASSWORD, and that the db service is healthy."
            ),
        )
        sys.exit(1)

    # ── 3. Initialize database schema ────────────────────────────────────
    # create_tables() is idempotent (CREATE IF NOT EXISTS).
    # The migration SQL in init-scripts/ handles first boot; this is a safety net.
    try:
        await create_tables()
        logger.info("database_schema_ready")
    except Exception as exc:
        logger.error(
            "database_schema_init_failed",
            error=str(exc),
            hint=(
                "This usually means the database is reachable but the schema "
                "could not be created. Check for enum type mismatches or migration "
                "failures in the PostgreSQL logs."
            ),
        )
        sys.exit(1)

    # ── 4. Bootstrap admin user ──────────────────────────────────────────
    # Uses pg_advisory_xact_lock to serialize across multiple workers.
    # Idempotent: no-ops if the admin user already exists.
    from database import AsyncSessionLocal
    from routers.auth import ensure_admin_exists

    try:
        async with AsyncSessionLocal() as db:
            await ensure_admin_exists(db)
    except Exception as exc:
        logger.error(
            "admin_bootstrap_failed",
            error=str(exc),
            hint=(
                "Could not seed the admin user. Check for enum mismatches, "
                "missing migrations, or incorrect INITIAL_ADMIN_PASSWORD."
            ),
        )
        sys.exit(1)

    logger.info("greenops_ready", host="0.0.0.0", port=8000, environment=settings.ENV)

    yield  # ── Application serves requests ──────────────────────────────

    # ── Shutdown ─────────────────────────────────────────────────────────
    logger.info("greenops_shutting_down")
    await engine.dispose()
    logger.info("greenops_stopped")


# ── Application factory ───────────────────────────────────────────────────────

def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="GreenOps API",
        description="Green IT Infrastructure Monitoring Platform",
        version="2.0.0",
        docs_url="/api/docs"     if settings.ENV != "production" else None,
        redoc_url="/api/redoc"   if settings.ENV != "production" else None,
        openapi_url="/api/openapi.json" if settings.ENV != "production" else None,
        lifespan=lifespan,
    )

    # Middleware is applied in reverse order: last added = first executed.
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
        max_age=600,
    )
    app.add_middleware(RateLimitMiddleware)

    app.include_router(auth.router,      prefix="/api/auth",      tags=["Authentication"])
    app.include_router(agents.router,    prefix="/api/agents",    tags=["Agents"])
    app.include_router(machines.router,  prefix="/api/machines",  tags=["Machines"])
    app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])

    @app.get("/health", tags=["Health"])
    async def health_check():
        """
        Health check endpoint. Used by:
          - Docker Compose healthcheck for the server service
          - nginx health probe (passes through to verify full proxy chain)
          - External monitoring tools
        """
        from database import AsyncSessionLocal
        from sqlalchemy import text as sql_text

        try:
            async with AsyncSessionLocal() as db:
                await db.execute(sql_text("SELECT 1"))
            db_status = "healthy"
        except Exception as db_exc:
            logger.warning("health_check_db_failed", error=str(db_exc))
            db_status = "unhealthy"

        overall = "healthy" if db_status == "healthy" else "degraded"

        return {
            "status": overall,
            "version": "2.0.0",
            "database": db_status,
            "timestamp": time.time(),
        }

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc):
        return JSONResponse(
            status_code=404,
            content={"error": "not_found", "message": "The requested resource was not found."},
        )

    @app.exception_handler(500)
    async def internal_error_handler(request: Request, exc):
        logger.error("unhandled_exception", path=request.url.path, error=str(exc))
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "message": "An unexpected error occurred.",
            },
        )

    return app


app = create_app()
