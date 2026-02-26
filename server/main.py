"""
GreenOps Server — Production-ready FastAPI application

Startup sequence (lifespan):
  1. Validate required environment variables (raises on config errors)
  2. Wait for PostgreSQL with exponential backoff
  3. Verify schema is present (does NOT create DDL — see database.py)
  4. Bootstrap admin user (idempotent, multi-worker-safe via pg_advisory_xact_lock)
  5. Yield (application serves requests)
  6. Shutdown: dispose engine, flush logs

Gunicorn worker failure policy:
  - sys.exit() is NEVER called inside lifespan. It kills the master process
    and takes down all workers. Instead, exceptions propagate normally and
    Gunicorn handles individual worker failures with its restart policy.
  - Configuration errors (missing JWT_SECRET_KEY) raise ValueError.
  - DB connectivity failures raise RuntimeError.
  - Schema missing raises RuntimeError.
  - Gunicorn will restart failed workers up to worker_max_restarts times.
"""
import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from config import get_settings
from database import verify_schema, engine
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
    max_attempts: int = 15,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
) -> None:
    """
    Wait for PostgreSQL to accept connections, with exponential backoff.

    Raises RuntimeError if all attempts are exhausted.
    Does NOT call sys.exit() — lets Gunicorn handle the worker failure.

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

    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            async with engine.connect() as conn:
                await conn.execute(sql_text("SELECT 1"))
            logger.info("database_connected", attempt=attempt)
            return

        except Exception as exc:
            last_error = exc
            if attempt >= max_attempts:
                break

            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            logger.warning(
                "database_not_ready",
                attempt=attempt,
                max_attempts=max_attempts,
                retry_in_seconds=round(delay, 1),
                error=str(exc),
            )
            await asyncio.sleep(delay)

    raise RuntimeError(
        f"Could not connect to PostgreSQL after {max_attempts} attempts. "
        f"Last error: {last_error}. "
        "Verify DATABASE_URL, POSTGRES_PASSWORD, and that the db service is healthy."
    )


# ── ASGI lifespan ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    ASGI lifespan handler. Runs startup logic before the first request
    and cleanup logic after the last.

    Error handling policy
    ─────────────────────
    Exceptions raised here propagate to Gunicorn, which marks the worker as
    failed and restarts it (up to max_requests / worker_max_restarts limits).
    We NEVER call sys.exit() — that would kill the master process.

    Gunicorn multi-worker note
    ─────────────────────────
    With preload_app=True (see gunicorn.conf.py), the master process runs this
    lifespan ONCE. Workers are forked after startup completes and inherit the
    already-initialized state. ensure_admin_exists() is called exactly once.
    """
    settings = get_settings()
    logger.info("greenops_starting", version="2.0.0", environment=settings.ENV)

    # ── 1. Validate configuration ─────────────────────────────────────────
    # Raises ValueError on hard config errors. Let it propagate so the
    # container exits with a non-zero code and a clear error message.
    issues = settings.validate()
    if issues:
        for issue in issues:
            logger.error("config_validation_failed", issue=issue)
        raise ValueError(
            f"Configuration errors prevent startup: {'; '.join(issues)}. "
            "Fix the issues in .env and restart."
        )

    # ── 2. Wait for database ──────────────────────────────────────────────
    # Raises RuntimeError if DB is unreachable after all retries.
    await _wait_for_database(max_attempts=15, base_delay=2.0)

    # ── 3. Verify schema ──────────────────────────────────────────────────
    # Raises RuntimeError if required tables are missing.
    # Does NOT run any DDL — see database.py for rationale.
    try:
        await verify_schema()
    except RuntimeError as exc:
        logger.error(
            "schema_verification_failed",
            error=str(exc),
            hint=(
                "Run migrations before starting the app: "
                "docker compose run --rm migrate"
            ),
        )
        raise

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
        raise

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
