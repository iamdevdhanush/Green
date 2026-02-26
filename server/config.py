"""
GreenOps Server Configuration
==============================
All configuration is read from environment variables.
Sensitive values (JWT_SECRET_KEY, POSTGRES_PASSWORD) have no defaults
in production and will cause a loud failure at startup if absent.

INITIAL_ADMIN_PASSWORD defaults to "admin123" (the documented default).
A warning is emitted in production if this default has not been changed.
"""

import secrets
import warnings
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Environment ──────────────────────────────────────────────────────────
    ENV: str = "production"
    DEBUG: bool = False

    # ── Database ─────────────────────────────────────────────────────────────
    # Set by docker-compose.yml as:
    #   postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
    # Never set DATABASE_URL manually in .env — docker-compose assembles it.
    DATABASE_URL: str = "postgresql+asyncpg://greenops:changeme@db:5432/greenops"

    # ── JWT ──────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = ""         # REQUIRED in production. Validated in validate().
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ── CORS ─────────────────────────────────────────────────────────────────
    CORS_ORIGINS: str = "http://localhost"

    # ── Rate limiting ────────────────────────────────────────────────────────
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    LOGIN_RATE_LIMIT_REQUESTS: int = 10
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 300

    # ── Energy calculations ──────────────────────────────────────────────────
    IDLE_POWER_WATTS: float = 65.0
    ACTIVE_POWER_WATTS: float = 120.0
    ELECTRICITY_COST_PER_KWH: float = 0.12
    IDLE_THRESHOLD_SECONDS: int = 300
    OFFLINE_THRESHOLD_SECONDS: int = 180
    MAX_HEARTBEAT_AGE_SECONDS: int = 3600 * 24 * 90

    # ── Admin bootstrap ───────────────────────────────────────────────────────
    # Default credentials are admin / admin123 as documented.
    # The password is hashed on first startup and stored in the database.
    # Change the password from the dashboard after first login.
    # Do NOT leave INITIAL_ADMIN_PASSWORD empty — it will fall back to "admin123"
    # and emit a warning in production.
    INITIAL_ADMIN_USERNAME: str = "admin"
    INITIAL_ADMIN_PASSWORD: str = "admin123"

    # ── Server ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000
    WORKERS: int = 4

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse comma-separated CORS_ORIGINS into a list."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    def validate(self) -> List[str]:
        """
        Validate required settings. Returns a list of issue descriptions.
        An empty list means all required settings are present and valid.

        Called once at startup by main.py lifespan.
        """
        issues: List[str] = []

        # ── JWT_SECRET_KEY ────────────────────────────────────────────────
        if not self.JWT_SECRET_KEY:
            if self.ENV != "production":
                warnings.warn(
                    "JWT_SECRET_KEY not set. Auto-generating for this session. "
                    "Tokens will be invalidated on every restart. "
                    "Set JWT_SECRET_KEY in .env for a persistent key.",
                    RuntimeWarning,
                    stacklevel=2,
                )
                # Safe for dev only: auto-generate so the server can still start.
                object.__setattr__(self, "JWT_SECRET_KEY", secrets.token_urlsafe(48))
            else:
                issues.append(
                    "JWT_SECRET_KEY is required in production. "
                    "Generate with: python3 -c \"import secrets; print(secrets.token_urlsafe(48))\""
                )
        elif len(self.JWT_SECRET_KEY) < 32:
            issues.append(
                f"JWT_SECRET_KEY is too short ({len(self.JWT_SECRET_KEY)} chars). "
                "Minimum 32 characters required."
            )

        # ── INITIAL_ADMIN_PASSWORD ────────────────────────────────────────
        # Must be at least 8 characters. Default ("admin123") satisfies this.
        # We do NOT fail here — we warn, because the app is still functional.
        if not self.INITIAL_ADMIN_PASSWORD:
            # Env var was explicitly set to empty string. Reset to default.
            object.__setattr__(self, "INITIAL_ADMIN_PASSWORD", "admin123")
            warnings.warn(
                "INITIAL_ADMIN_PASSWORD is empty. Resetting to default 'admin123'. "
                "Change the password after first login.",
                RuntimeWarning,
                stacklevel=2,
            )
        elif len(self.INITIAL_ADMIN_PASSWORD) < 8:
            issues.append(
                f"INITIAL_ADMIN_PASSWORD is too short "
                f"({len(self.INITIAL_ADMIN_PASSWORD)} chars). Minimum 8 characters."
            )

        # ── Production warnings (non-fatal) ──────────────────────────────
        if self.ENV == "production":
            if self.INITIAL_ADMIN_PASSWORD == "admin123":
                warnings.warn(
                    "INITIAL_ADMIN_PASSWORD is set to the default 'admin123'. "
                    "Change this immediately after first login via the dashboard.",
                    RuntimeWarning,
                    stacklevel=2,
                )
            if "*" in self.cors_origins_list:
                warnings.warn(
                    "CORS_ORIGINS contains '*' in production. "
                    "Set it to your specific domain(s) to restrict access.",
                    RuntimeWarning,
                    stacklevel=2,
                )

        return issues


@lru_cache()
def get_settings() -> Settings:
    """
    Cached settings singleton. Constructed once per process lifetime.
    In tests, call get_settings.cache_clear() before each test.
    """
    return Settings()
