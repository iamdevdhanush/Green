"""
GreenOps Authentication Router
- Login with username/password -> access + refresh tokens
- Refresh token rotation
- Logout / revoke tokens
- Token verification and user info
- ensure_admin_exists: safe, idempotent, fully enum-correct
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

# Import UserRole from database — the single source of truth for this enum.
from database import RefreshToken, User, UserRole, get_db
from utils.auth import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    needs_rehash,
    verify_password,
)
from utils.security import get_current_user

logger = structlog.get_logger(__name__)
router = APIRouter()

ACCOUNT_LOCKOUT_THRESHOLD = 10
ACCOUNT_LOCKOUT_MINUTES = 15


# ---------------------------------------------------------------------------
# Helper: safely coerce a raw string or enum to UserRole
# ---------------------------------------------------------------------------

def _coerce_role(value) -> UserRole:
    """
    Accept a UserRole member OR a string and always return a UserRole member.

    Raises ValueError with a descriptive message if the value is not valid.

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
        # UserRole._missing_ handles case-insensitive normalisation
        return UserRole(value)
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
    ip_address = request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or (
        request.client.host if request.client else "unknown"
    )

    result = await db.execute(
        select(User).where(User.username == payload.username)
    )
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        # Perform a dummy verify to prevent timing attacks even when user not found
        verify_password("dummy", "$argon2id$v=19$m=65536,t=3,p=4$dummysaltdummysalt$dummyhashvalue00")
        logger.warning("login_failed_user_not_found", username=payload.username, ip=ip_address)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_credentials", "message": "Invalid username or password."},
        )

    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        wait_minutes = int(
            (user.locked_until - datetime.now(timezone.utc)).total_seconds() / 60
        ) + 1
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "account_locked",
                "message": f"Account locked. Try again in {wait_minutes} minutes.",
            },
        )

    if not verify_password(payload.password, user.password_hash):
        user.failed_login_attempts += 1

        if user.failed_login_attempts >= ACCOUNT_LOCKOUT_THRESHOLD:
            user.locked_until = datetime.now(timezone.utc) + timedelta(
                minutes=ACCOUNT_LOCKOUT_MINUTES
            )
            user.failed_login_attempts = 0
            logger.warning("account_locked", username=payload.username, ip=ip_address)

        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_credentials", "message": "Invalid username or password."},
        )

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.now(timezone.utc)

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)

    # Safely coerce role to UserRole enum then extract string value for JWT
    role_enum = _coerce_role(user.role)
    role_value = role_enum.value  # always "admin" or "viewer"

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
# Startup helper
# ---------------------------------------------------------------------------

async def ensure_admin_exists(db: AsyncSession) -> None:
    """
    Idempotent bootstrap function.

    Guarantees exactly one admin user exists at startup.

    Safety guarantees
    -----------------
    - If the admin user already exists → returns immediately, no DB write.
    - role is ALWAYS set to UserRole.ADMIN (the enum member), never a string.
    - IntegrityError (duplicate username race condition) is caught and swallowed.
    - DBAPIError (enum mismatch, DB not ready, etc.) is caught, logged with
      full details, then re-raised so the caller (lifespan) can fail fast.
    - All DB operations are wrapped in try/except with explicit rollback.
    """
    from config import get_settings
    settings = get_settings()

    try:
        # ── 1. Verify the user_role enum exists in PostgreSQL ──────────────
        try:
            await db.execute(text("SELECT 'admin'::user_role"))
        except DBAPIError as exc:
            logger.error(
                "startup_enum_check_failed",
                detail=(
                    "PostgreSQL user_role enum is missing or does not contain 'admin'. "
                    "Run migration 001_initial_schema.sql to create it."
                ),
                original_error=str(exc),
            )
            await db.rollback()
            raise

        # ── 2. Check whether admin already exists ─────────────────────────
        result = await db.execute(
            select(User).where(User.username == settings.INITIAL_ADMIN_USERNAME)
        )
        existing = result.scalar_one_or_none()

        if existing:
            logger.info(
                "admin_already_exists",
                username=settings.INITIAL_ADMIN_USERNAME,
                role=_coerce_role(existing.role).value,
            )
            return  # nothing to do — idempotent

        # ── 3. Determine password ──────────────────────────────────────────
        admin_password = settings.INITIAL_ADMIN_PASSWORD
        if not admin_password:
            import secrets as _secrets
            admin_password = _secrets.token_urlsafe(16)
            logger.warning(
                "generated_random_admin_password",
                password=admin_password,
                hint="Set INITIAL_ADMIN_PASSWORD in .env to avoid this.",
            )

        # ── 4. Create admin with explicit UserRole.ADMIN enum member ───────
        #
        #   DO NOT use role="ADMIN" or role="admin" here.
        #   UserRole.ADMIN is the enum *member*; SQLAlchemy + values_callable
        #   will translate it to the string "admin" when talking to PostgreSQL.
        #
        admin = User(
            username=settings.INITIAL_ADMIN_USERNAME,
            password_hash=hash_password(admin_password),
            role=UserRole.ADMIN,   # ← enum member, never a raw string
            is_active=True,
        )

        db.add(admin)
        await db.commit()
        logger.info(
            "admin_user_created",
            username=settings.INITIAL_ADMIN_USERNAME,
            role=UserRole.ADMIN.value,  # logs "admin"
        )

    except IntegrityError:
        # Race condition: another worker created the admin between our SELECT
        # and INSERT.  This is harmless — swallow and continue.
        await db.rollback()
        logger.info(
            "admin_creation_race_condition_handled",
            username=settings.INITIAL_ADMIN_USERNAME,
        )

    except DBAPIError as exc:
        await db.rollback()
        logger.error(
            "ensure_admin_exists_db_error",
            error=str(exc),
            detail=(
                "A database-level error occurred while creating the admin user. "
                "Common causes: enum mismatch (value 'ADMIN' sent instead of 'admin'), "
                "DB not ready, or missing migration."
            ),
        )
        raise  # propagate to lifespan so the server fails fast with a clear error

    except Exception as exc:
        await db.rollback()
        logger.error("ensure_admin_exists_unexpected_error", error=str(exc))
        raise
