"""
GreenOps API — Main Application Entry Point
Enterprise infrastructure energy intelligence platform.
"""
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.api.v1.router import router as api_router
from app.middleware.rate_limit import limiter

configure_logging(debug=settings.APP_DEBUG)
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("greenops_startup", version="1.0.0", env=settings.APP_ENV)
    yield
    log.info("greenops_shutdown")


app = FastAPI(
    title="GreenOps API",
    description="Enterprise Infrastructure Energy Intelligence Platform",
    version="1.0.0",
    docs_url="/api/docs" if settings.APP_ENV != "production" else None,
    redoc_url="/api/redoc" if settings.APP_ENV != "production" else None,
    lifespan=lifespan,
)

# ── Rate limiting ──────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ───────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request timing ─────────────────────────────────────────────────────────
@app.middleware("http")
async def request_timing(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    response.headers["X-Response-Time"] = f"{duration:.4f}s"
    return response


# ── Centralized exception handler ──────────────────────────────────────────
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    log.error("unhandled_exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


# ── Health check ───────────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
def health():
    return {"status": "healthy", "app": settings.APP_NAME, "version": "1.0.0"}


# ── Prometheus metrics ─────────────────────────────────────────────────────
try:
    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
except Exception:
    pass


# ── Routes ─────────────────────────────────────────────────────────────────
app.include_router(api_router)
