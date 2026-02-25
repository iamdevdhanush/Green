"""
GreenOps Server Configuration
==============================
All configuration is read from environment variables.
No defaults for security-sensitive values in production.
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
    DATABASE_URL: str = "postgresql+asyncpg://greenops:changeme@db:5432/greenops"

    # ── JWT ──────────────────────────────────────────────────────────────────
    # No default — must be set in .env. Validated in validate().
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ── CORS ─────────────────────────────────────────────────────────────────
    # Comma-separated list of allowed origins.
    # In production, set this explicitly to your domain: https://app.example.com
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
    INITIAL_ADMIN_USERNAME: str = "admin"
    # No default — must be set in .env. Validated in validate().
    INITIAL_ADMIN_PASSWORD: str = ""

    # ── Server ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000
    WORKERS: int = 4

    class Config:
        env_file = ".env"
        case_sensitive = True
        # Allow extra fields — do not fail if .env has unknown vars
        extra = "ignore"

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse comma-separated CORS_ORIGINS into a list."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    def validate(self) -> List[str]:
        """
        Validate required settings for production.

        Returns a list of missing/invalid setting names.
        An empty list means all required settings are present and valid.
        """
        issues: List[str] = []

        # JWT_SECRET_KEY: required, must be at least 32 chars
        if not self.JWT_SECRET_KEY:
            if self.ENV != "production":
                # Dev convenience: auto-generate a key and warn loudly
                warnings.warn(
                    "JWT_SECRET_KEY not set. Generating random key. "
                    "Tokens will be invalidated on restart. Set JWT_SECRET_KEY in .env.",
                    RuntimeWarning,
                    stacklevel=2,
                )
                # Mutate is OK here — Settings is a Pydantic model, but we're
                # modifying the instance before it's used for auth operations.
                object.__setattr__(self, "JWT_SECRET_KEY", secrets.token_urlsafe(48))
            else:
                issues.append("JWT_SECRET_KEY (required in production, min 32 chars)")
        elif len(self.JWT_SECRET_KEY) < 32:
            issues.append(f"JWT_SECRET_KEY is too short ({len(self.JWT_SECRET_KEY)} chars, min 32)")

        # INITIAL_ADMIN_PASSWORD: required, min 8 chars
        if not self.INITIAL_ADMIN_PASSWORD:
            issues.append("INITIAL_ADMIN_PASSWORD (required, min 8 chars)")
        elif len(self.INITIAL_ADMIN_PASSWORD) < 8:
            issues.append(
                f"INITIAL_ADMIN_PASSWORD is too short "
                f"({len(self.INITIAL_ADMIN_PASSWORD)} chars, min 8)"
            )

        # Warn (not fail) if CORS is wildcard in production
        if self.ENV == "production" and "*" in self.cors_origins_list:
            warnings.warn(
                "CORS_ORIGINS contains '*' in production. "
                "Set it to your specific domain(s).",
                RuntimeWarning,
                stacklevel=2,
            )

        return issues


@lru_cache()
def get_settings() -> Settings:
    """
    Cached settings singleton.
    The cache means Settings() is only constructed once per process lifetime.
    In tests, call get_settings.cache_clear() to reset between tests.
    """
    return Settings()"""
GreenOps Server Configuration
==============================
All configuration is read from environment variables.
No defaults for security-sensitive values in production.
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
    DATABASE_URL: str = "postgresql+asyncpg://greenops:changeme@db:5432/greenops"

    # ── JWT ──────────────────────────────────────────────────────────────────
    # No default — must be set in .env. Validated in validate().
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ── CORS ─────────────────────────────────────────────────────────────────
    # Comma-separated list of allowed origins.
    # In production, set this explicitly to your domain: https://app.example.com
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
    INITIAL_ADMIN_USERNAME: str = "admin"
    # No default — must be set in .env. Validated in validate().
    INITIAL_ADMIN_PASSWORD: str = ""

    # ── Server ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000
    WORKERS: int = 4

    class Config:
        env_file = ".env"
        case_sensitive = True
        # Allow extra fields — do not fail if .env has unknown vars
        extra = "ignore"

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse comma-separated CORS_ORIGINS into a list."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    def validate(self) -> List[str]:
        """
        Validate required settings for production.

        Returns a list of missing/invalid setting names.
        An empty list means all required settings are present and valid.
        """
        issues: List[str] = []

        # JWT_SECRET_KEY: required, must be at least 32 chars
        if not self.JWT_SECRET_KEY:
            if self.ENV != "production":
                # Dev convenience: auto-generate a key and warn loudly
                warnings.warn(
                    "JWT_SECRET_KEY not set. Generating random key. "
                    "Tokens will be invalidated on restart. Set JWT_SECRET_KEY in .env.",
                    RuntimeWarning,
                    stacklevel=2,
                )
                # Mutate is OK here — Settings is a Pydantic model, but we're
                # modifying the instance before it's used for auth operations.
                object.__setattr__(self, "JWT_SECRET_KEY", secrets.token_urlsafe(48))
            else:
                issues.append("JWT_SECRET_KEY (required in production, min 32 chars)")
        elif len(self.JWT_SECRET_KEY) < 32:
            issues.append(f"JWT_SECRET_KEY is too short ({len(self.JWT_SECRET_KEY)} chars, min 32)")

        # INITIAL_ADMIN_PASSWORD: required, min 8 chars
        if not self.INITIAL_ADMIN_PASSWORD:
            issues.append("INITIAL_ADMIN_PASSWORD (required, min 8 chars)")
        elif len(self.INITIAL_ADMIN_PASSWORD) < 8:
            issues.append(
                f"INITIAL_ADMIN_PASSWORD is too short "
                f"({len(self.INITIAL_ADMIN_PASSWORD)} chars, min 8)"
            )

        # Warn (not fail) if CORS is wildcard in production
        if self.ENV == "production" and "*" in self.cors_origins_list:
            warnings.warn(
                "CORS_ORIGINS contains '*' in production. "
                "Set it to your specific domain(s).",
                RuntimeWarning,
                stacklevel=2,
            )

        return issues


@lru_cache()
def get_settings() -> Settings:
    """
    Cached settings singleton.
    The cache means Settings() is only constructed once per process lifetime.
    In tests, call get_settings.cache_clear() to reset between tests.
    """
    return Settings()
