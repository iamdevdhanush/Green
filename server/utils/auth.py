"""
GreenOps Authentication Router
================================
Endpoints
---------
  POST /api/auth/login     — exchange credentials for access + refresh tokens
  POST /api/auth/refresh   — rotate refresh token, get new access token
  POST /api/auth/logout    — revoke refresh token
  GET  /api/auth/verify    — validate current access token
  GET  /api/auth/me        — current user info

Startup helper
--------------
  ensure_admin_exists(db)  — idempotent, multi-worker-safe admin bootstrap

Multi-worker safety
-------------------
Gunicorn spawns N UvicornWorker processes; each runs the ASGI lifespan
independently, so ensure_admin_exists() is called N times concurrently.
We serialize via a PostgreSQL session-level advisory lock so exactly one
worker performs the INSERT; the rest detect the already-existing row and
return immediately without touching the database.
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
ACCOUNT_LOCKOUT_MINUTES = 15

# Arbitrary but stable integer key for pg_advisory_xact_lock.
# Must be the same across all workers in the same PostgreSQL database.
# Range: any 64-bit signed integer. We use a fixed constant derived from
# the ASCII sum of "greenops_admin_init" for readability.
_ADMIN_INIT_LOCK_KEY: int = 0x6772656E6F707361  # "greenopsa" in hex


# ---------------------------------------------------------------------------
# Helper: safely coerce a raw string or enum to UserRole
# ---------------------------------------------------------------------------

def _coerce_role(value) -> UserRole:
    """
    Accept a UserRole member OR a string and always return a UserRole member.

    Examples
    --------
    _coerce_role(UserRole.ADMIN)  -> UserRole.ADMIN
    _coerce_role("admin")         -> UserRole.ADMIN
    _coerce_role("ADMIN")         -> UserRole.ADMIN  (normalised via _missing_)
    _coerce_role("superuser")     -> raises ValueError
    """
    if isinstance(value, UserRole):
        return value
    if isinstance(value, str):
        return UserRole(value)   # _missing_ handles case-insensitive normalisation
    raise ValueError(f"Cannot coerce type {type(value)!r} to UserRole")


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
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_at: datetime
    role: str
    username: str


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


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
    # IMPORTANT: always call timing_safe_dummy_verify() before returning 401
    # so that "user not found" and "wrong password" paths take the same time.
    if not user or not user.is_active:
        timing_safe_dummy_verify()           # ← real Argon2 computation, not a no-op
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
        # No timing_safe_dummy_verify needed here; lockout status doesn't leak
        # whether the password would have been correct.
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

    # Silently upgrade hash if parameters have changed since it was stored.
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
            detail={"error": "user_inactive", "message": "User inactive."},
        )

    # Token rotation: revoke old, issue new access token.
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
    """Verify the current access token is valid."""
    role_value = _coerce_role(current_user.role).value
    return {
        "valid": True,
        "username": current_user.username,
        "role": role_value,
    }


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user info."""
    role_value = _coerce_role(current_user.role).value
    return {
        "id": current_user.id,
        "username": current_user.username,
        "role": role_value,
        "last_login": current_user.last_login,
        "created_at": current_user.created_at,
    }


# ---------------------------------------------------------------------------
# Startup helper — idempotent, multi-worker-safe admin bootstrap
# ---------------------------------------------------------------------------

async def ensure_admin_exists(db: AsyncSession) -> None:
    """
    Guarantee exactly one admin user exists. Safe to call concurrently from
    multiple Gunicorn workers because it uses a PostgreSQL session-level
    advisory lock to serialize the check-then-insert operation.

    Advisory lock guarantee
    -----------------------
    pg_advisory_xact_lock(key) blocks until the lock is acquired and releases
    it automatically at the end of the transaction. Because all workers share
    the same PostgreSQL server, exactly one worker proceeds at a time.

    Timeline (4 workers, no existing admin):
      W1 acquires lock → SELECT → None → INSERT → COMMIT (lock released)
      W2 acquires lock → SELECT → finds row created by W1 → returns early
      W3, W4: same as W2.

    This eliminates the original race where all workers concurrently:
      - Saw no admin (SELECT returned None before W1 committed)
      - Generated different random passwords
      - All tried INSERT; only W1 succeeded
      - W2-W4 rolled back with their passwords discarded
      - User saw 4 confusing log lines and couldn't know which password was stored.

    Password determinism
    --------------------
    INITIAL_ADMIN_PASSWORD must be set in .env for production. If it is empty
    we generate a random password, log it prominently, and log it ONLY ONCE
    (inside the lock, after confirming we're the worker doing the INSERT).
    """
    from config import get_settings
    settings = get_settings()

    try:
        # ── Step 0: Verify the PostgreSQL enum exists (schema sanity check) ──
        try:
            await db.execute(text("SELECT 'admin'::user_role"))
        except DBAPIError as exc:
            logger.error(
                "startup_enum_check_failed",
                detail=(
                    "PostgreSQL user_role enum is missing or doesn't contain 'admin'. "
                    "Run migration 001_initial_schema.sql."
                ),
                original_error=str(exc),
            )
            await db.rollback()
            raise

        # ── Step 1: Acquire a session-level advisory lock ─────────────────
        # This serialises all workers. The lock is held until db.commit() or
        # db.rollback() — whichever happens first in this function.
        await db.execute(text(f"SELECT pg_advisory_xact_lock({_ADMIN_INIT_LOCK_KEY})"))

        # ── Step 2: Re-check for existing admin AFTER acquiring the lock ──
        # (Another worker may have created it between our initial check and
        # lock acquisition — the lock ensures we see the committed state.)
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
            )
            # Commit releases the advisory lock.
            await db.commit()
            return

        # ── Step 3: Determine the password ───────────────────────────────
        admin_password = settings.INITIAL_ADMIN_PASSWORD
        generated_password = False

        if not admin_password:
            import secrets as _secrets
            admin_password = _secrets.token_urlsafe(16)
            generated_password = True
            # Log BEFORE hashing so the plaintext appears in logs.
            # This only runs in one worker (inside the lock).
            logger.warning(
                "admin_password_auto_generated",
                password=admin_password,
                username=admin_username,
                action_required=(
                    "Set INITIAL_ADMIN_PASSWORD in .env to avoid this. "
                    "This password will NOT be logged again."
                ),
            )

        # ── Step 4: Create the admin user ─────────────────────────────────
        admin = User(
            username=admin_username,              # always lowercase
            password_hash=hash_password(admin_password),
            role=UserRole.ADMIN,                  # enum member, not a raw string
            is_active=True,
        )
        db.add(admin)

        # Commit also releases the pg_advisory_xact_lock.
        await db.commit()

        logger.info(
            "admin_user_created",
            username=admin_username,
            role=UserRole.ADMIN.value,
            password_source="auto_generated" if generated_password else "INITIAL_ADMIN_PASSWORD",
        )

    except IntegrityError:
        # Extremely unlikely given the advisory lock, but handle anyway:
        # a concurrent INSERT slipped through (e.g. direct DB manipulation).
        await db.rollback()
        logger.info(
            "admin_creation_skipped_integrity_error",
            username=settings.INITIAL_ADMIN_USERNAME.strip().lower(),
            reason="row already existed by the time we tried to insert",
        )

    except DBAPIError as exc:
        await db.rollback()
        logger.error(
            "ensure_admin_exists_db_error",
            error=str(exc),
            detail=(
                "DB-level error during admin bootstrap. Common causes: "
                "enum mismatch, DB not ready, missing migration."
            ),
        )
        raise  # propagate — lifespan will call sys.exit(1)

    except Exception as exc:
        await db.rollback()
        logger.error("ensure_admin_exists_unexpected_error", error=str(exc))
        raise
