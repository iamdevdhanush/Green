"""
GreenOps Server Configuration
All settings loaded from environment variables with validation.
"""
import os
import secrets
from functools import lru_cache
from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Environment
    ENV: str = "development"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://greenops:greenops@localhost:5432/greenops"

    # Security - MUST be set in production
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:80,http://localhost"

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    LOGIN_RATE_LIMIT_REQUESTS: int = 10
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 300  # 5 minutes

    # Energy Calculation
    IDLE_POWER_WATTS: float = 65.0
    ACTIVE_POWER_WATTS: float = 120.0
    ELECTRICITY_COST_PER_KWH: float = 0.12

    # Agent Settings
    IDLE_THRESHOLD_SECONDS: int = 300  # 5 minutes
    OFFLINE_THRESHOLD_SECONDS: int = 180  # 3 minutes
    MAX_HEARTBEAT_AGE_SECONDS: int = 3600 * 24 * 90  # 90 days retention

    # Admin (initial admin user - only used on first startup)
    INITIAL_ADMIN_USERNAME: str = "admin"
    INITIAL_ADMIN_PASSWORD: str = ""  # MUST be set via env var

    # Logging
    LOG_LEVEL: str = "INFO"

    # Server
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000
    WORKERS: int = 4

    class Config:
        env_file = ".env"
        case_sensitive = True

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    def validate(self) -> List[str]:
        """Validate critical settings. Returns list of missing/invalid settings."""
        missing = []

        if self.ENV == "production":
            if not self.JWT_SECRET_KEY or len(self.JWT_SECRET_KEY) < 32:
                missing.append("JWT_SECRET_KEY (must be at least 32 chars)")
            if not self.INITIAL_ADMIN_PASSWORD or len(self.INITIAL_ADMIN_PASSWORD) < 12:
                missing.append("INITIAL_ADMIN_PASSWORD (must be at least 12 chars)")

        # Auto-generate JWT secret in non-production if not set (with warning)
        if not self.JWT_SECRET_KEY:
            import warnings
            warnings.warn(
                "JWT_SECRET_KEY not set. Generating random key. "
                "THIS IS INSECURE FOR PRODUCTION - all tokens will be invalidated on restart.",
                stacklevel=2,
            )
            self.JWT_SECRET_KEY = secrets.token_urlsafe(48)

        return missing


@lru_cache()
def get_settings() -> Settings:
    return Settings()
