"""
GreenOps Authentication Router
================================
Endpoints:
  POST /api/auth/login     — exchange credentials for access + refresh tokens
  POST /api/auth/refresh   — rotate refresh token, get new access token
  POST /api/auth/logout    — revoke refresh token
  GET  /api/auth/verify    — validate current access token
  GET  /api/auth/me        — current user info

Startup helper:
  ensure_admin_exists(db)  — idempotent, multi-worker-safe admin bootstrap

Admin seeding policy:
  - Default credentials: admin / admin123 (documented, deterministic)
  - Password is hashed with Argon2id and stored in the database
  - If admin already exists, NO changes are made — existing password preserved
  - Credentials are NEVER auto-generated or randomly changed
  - Password must be changed from the dashboard settings after first login
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from database import RefreshToken, User, UserRole, get_db
from utils.auth import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    needs_rehash,
    timing_safe_dummy_verify,
    verify_password,
)
from utils.security import get_current_user

logger = structlog.get_logger(__name__)
router = APIRouter()

ACCOUNT_LOCKOUT_THRESHOLD = 10
ACCOUNT_LOCKOUT_MINUTES   = 15

# Stable advisory lock key — same value across all workers in the same DB instance.
# Any 64-bit signed integer; this spells "greenopsa" in hex.
_ADMIN_INIT_LOCK_KEY: int = 0x6772656E6F707361


# ---------------------------------------------------------------------------
# Helper: coerce raw string or enum to UserRole
# ---------------------------------------------------------------------------

def _coerce_role(value) -> UserRole:
    """
    Accept a UserRole member OR a string and return a UserRole member.
    Normalises case via UserRole._missing_().

    Examples:
        _coerce_role(UserRole.ADMIN)  → UserRole.ADMIN
        _coerce_role("admin")         → UserRole.ADMIN
        _coerce_role("ADMIN")         → UserRole.ADMIN  (normalised)
        _coerce_role("superuser")     → raises ValueError
    """
    if isinstance(value, UserRole):
        return value
    if isinstance(value, str):
        return UserRole(value)
    raise ValueError(f"Cannot coerce {type(value)!r} to UserRole")


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=256)

    @field_validator("username")
    @classmethod
    def sanitize_username(cls, v: str) -> str:
        return v.strip().lower()


class LoginResponse(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"
    expires_at:    datetime
    role:          str
    username:      str


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    expires_at:   datetime


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    ip_address = (
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )

    # ── 1. Fetch user ──────────────────────────────────────────────────────
    result = await db.execute(
        select(User).where(User.username == payload.username)
    )
    user = result.scalar_one_or_none()

    # ── 2. Unknown user / inactive ─────────────────────────────────────────
    # Always call timing_safe_dummy_verify() before returning 401 so that
    # "user not found" and "wrong password" paths take the same time (~100ms).
    # Without this, username enumeration is trivial via timing.
    if not user or not user.is_active:
        timing_safe_dummy_verify()
        logger.warning(
            "login_failed",
            reason="user_not_found_or_inactive",
            username=payload.username,
            ip=ip_address,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_credentials", "message": "Invalid username or password."},
        )

    # ── 3. Account lockout check ───────────────────────────────────────────
    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        wait_minutes = (
            int((user.locked_until - datetime.now(timezone.utc)).total_seconds() / 60) + 1
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "account_locked",
                "message": f"Account locked. Try again in {wait_minutes} minutes.",
            },
        )

    # ── 4. Password verification ───────────────────────────────────────────
    if not verify_password(payload.password, user.password_hash):
        user.failed_login_attempts += 1

        if user.failed_login_attempts >= ACCOUNT_LOCKOUT_THRESHOLD:
            user.locked_until = datetime.now(timezone.utc) + timedelta(
                minutes=ACCOUNT_LOCKOUT_MINUTES
            )
            user.failed_login_attempts = 0
            logger.warning("account_locked", username=payload.username, ip=ip_address)

        await db.commit()
        logger.warning(
            "login_failed",
            reason="wrong_password",
            username=payload.username,
            attempts=user.failed_login_attempts,
            ip=ip_address,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_credentials", "message": "Invalid username or password."},
        )

    # ── 5. Successful authentication ───────────────────────────────────────
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.now(timezone.utc)

    # Silently upgrade hash if Argon2id parameters have changed.
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)
        logger.info("password_rehashed", username=user.username)

    role_value = _coerce_role(user.role).value

    access_token, expires_at = create_access_token(
        user_id=user.id,
        username=user.username,
        role=role_value,
    )
    raw_refresh, refresh_hash, refresh_expires = create_refresh_token()

    db_refresh = RefreshToken(
        user_id=user.id,
        token_hash=refresh_hash,
        expires_at=refresh_expires,
        user_agent=request.headers.get("User-Agent", "")[:256],
        ip_address=ip_address[:64],
    )
    db.add(db_refresh)
    await db.commit()

    logger.info("login_success", username=user.username, ip=ip_address)

    return LoginResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        expires_at=expires_at,
        role=role_value,
        username=user.username,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    token_hash = hash_refresh_token(payload.refresh_token)

    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked == False,
        )
    )
    db_token = result.scalar_one_or_none()

    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_token", "message": "Invalid or expired refresh token."},
        )

    if db_token.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        db_token.revoked = True
        db_token.revoked_at = datetime.now(timezone.utc)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "token_expired", "message": "Refresh token expired."},
        )

    result = await db.execute(
        select(User).where(
            User.id == db_token.user_id,
            User.is_active == True,
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "user_inactive", "message": "User inactive or not found."},
        )

    # Token rotation: revoke old token, issue new access token.
    db_token.revoked = True
    db_token.revoked_at = datetime.now(timezone.utc)

    role_value = _coerce_role(user.role).value
    access_token, expires_at = create_access_token(
        user_id=user.id,
        username=user.username,
        role=role_value,
    )
    await db.commit()

    return TokenResponse(access_token=access_token, expires_at=expires_at)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: RefreshRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    token_hash = hash_refresh_token(payload.refresh_token)

    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.user_id == current_user.id,
        )
    )
    db_token = result.scalar_one_or_none()

    if db_token:
        db_token.revoked = True
        db_token.revoked_at = datetime.now(timezone.utc)
        await db.commit()

    logger.info("logout", username=current_user.username)


@router.get("/verify")
async def verify_token(current_user: User = Depends(get_current_user)):
    """Verify the current access token is valid and return basic user info."""
    role_value = _coerce_role(current_user.role).value
    return {"valid": True, "username": current_user.username, "role": role_value}


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the current authenticated user's profile."""
    role_value = _coerce_role(current_user.role).value
    return {
        "id":         current_user.id,
        "username":   current_user.username,
        "role":       role_value,
        "last_login": current_user.last_login,
        "created_at": current_user.created_at,
    }


# ---------------------------------------------------------------------------
# Startup helper — idempotent, multi-worker-safe admin bootstrap
# ---------------------------------------------------------------------------

async def ensure_admin_exists(db: AsyncSession) -> None:
    """
    Guarantee exactly one admin user exists with the configured credentials.
    Safe to call concurrently from multiple Gunicorn workers.

    Admin seeding policy
    ─────────────────────
    1. Default credentials: username=admin, password=admin123 (from .env defaults)
    2. If INITIAL_ADMIN_USERNAME / INITIAL_ADMIN_PASSWORD are set in .env, those
       values are used instead.
    3. If the admin user ALREADY EXISTS, this function makes NO changes.
       The existing password is preserved regardless of INITIAL_ADMIN_PASSWORD.
       To change the password, use the dashboard settings page.
    4. Credentials are NEVER auto-generated. If INITIAL_ADMIN_PASSWORD is
       missing or empty, the code defaults to "admin123" (same as the config default).

    Multi-worker safety
    ─────────────────────
    pg_advisory_xact_lock(key) blocks until the lock is acquired and is released
    automatically at the end of the transaction. All workers share the same
    PostgreSQL server, so exactly one worker proceeds at a time.

    Timeline (4 Gunicorn workers, no existing admin):
      W1: acquires lock → SELECT None → INSERT → COMMIT → lock released
      W2: acquires lock → SELECT finds W1's row → returns immediately
      W3, W4: same as W2
    """
    from config import get_settings
    settings = get_settings()

    try:
        # ── Step 0: Sanity-check that the PostgreSQL enum type exists ──────
        # If the migration hasn't run, we get a clear error here rather than
        # a cryptic "invalid input value" failure later.
        try:
            await db.execute(text("SELECT 'admin'::user_role"))
        except DBAPIError as exc:
            logger.error(
                "startup_enum_check_failed",
                hint=(
                    "The 'user_role' PostgreSQL enum type does not exist or does "
                    "not contain 'admin'. Ensure migrations/init-scripts/01-initial-schema.sql "
                    "ran successfully on first boot."
                ),
                error=str(exc),
            )
            await db.rollback()
            raise

        # ── Step 1: Acquire PostgreSQL session-level advisory lock ────────
        # Serialises the check-then-insert across all concurrent workers.
        await db.execute(text(f"SELECT pg_advisory_xact_lock({_ADMIN_INIT_LOCK_KEY})"))

        # ── Step 2: Check for existing admin (with lock held) ─────────────
        admin_username = settings.INITIAL_ADMIN_USERNAME.strip().lower()

        result = await db.execute(
            select(User).where(User.username == admin_username)
        )
        existing = result.scalar_one_or_none()

        if existing:
            logger.info(
                "admin_already_exists",
                username=admin_username,
                role=_coerce_role(existing.role).value,
                note="Existing password is preserved. Use the dashboard to change it.",
            )
            await db.commit()
            return

        # ── Step 3: Determine password — NEVER auto-generate ─────────────
        # Use INITIAL_ADMIN_PASSWORD from .env; fall back to "admin123".
        # This is deterministic and reproducible across deployments.
        admin_password = settings.INITIAL_ADMIN_PASSWORD or "admin123"

        if admin_password == "admin123":
            logger.warning(
                "admin_using_default_password",
                username=admin_username,
                action_required="Change this password after first login via the dashboard.",
            )

        # ── Step 4: Create the admin user ─────────────────────────────────
        admin = User(
            username=admin_username,
            password_hash=hash_password(admin_password),
            role=UserRole.ADMIN,   # Always use the enum member, never a raw string
            is_active=True,
        )
        db.add(admin)

        # COMMIT also releases the pg_advisory_xact_lock.
        await db.commit()

        logger.info(
            "admin_user_created",
            username=admin_username,
            role=UserRole.ADMIN.value,
        )

    except IntegrityError:
        # Extremely rare with the advisory lock in place, but handled defensively.
        # A concurrent INSERT could happen if someone inserted outside this flow.
        await db.rollback()
        logger.info(
            "admin_creation_skipped",
            reason="IntegrityError — row already existed when we tried to insert.",
            username=settings.INITIAL_ADMIN_USERNAME.strip().lower(),
        )

    except DBAPIError as exc:
        await db.rollback()
        logger.error(
            "ensure_admin_exists_db_error",
            error=str(exc),
            hint=(
                "Database-level error during admin bootstrap. Common causes: "
                "enum type missing (run migrations), DB not accepting connections, "
                "schema mismatch."
            ),
        )
        raise  # Propagate — main.py lifespan will call sys.exit(1)

    except Exception as exc:
        await db.rollback()
        logger.error("ensure_admin_exists_unexpected_error", error=str(exc))
        raise
