"""
GreenOps Core Configuration
Validated Pydantic settings with environment variable loading.
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────
    APP_NAME: str = "GreenOps"
    APP_ENV: str = "development"
    APP_DEBUG: bool = False
    SECRET_KEY: str
    ALLOWED_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    # ── Database ───────────────────────────────────────────────
    DATABASE_URL: str

    # ── Redis ──────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── JWT ────────────────────────────────────────────────────
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWT_ALGORITHM: str = "HS256"

    # ── Rate Limiting ──────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 60
    AUTH_RATE_LIMIT_PER_MINUTE: int = 10

    # ── Energy Constants ───────────────────────────────────────
    IDLE_KWH_PER_HOUR: float = 0.12
    CO2_KG_PER_KWH: float = 0.386
    COST_PER_KWH: float = 0.12

    # ── Celery ─────────────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── Agent ──────────────────────────────────────────────────
    AGENT_IDLE_THRESHOLD_MINUTES: int = 15
    SHUTDOWN_COMMAND_TTL_SECONDS: int = 120


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
