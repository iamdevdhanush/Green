"""
GreenOps Authentication Router
- Login with username/password -> access + refresh tokens
- Refresh token rotation
- Logout / revoke tokens
- Token verification
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

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


# ============================
# Request / Response Models
# ============================

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


# ============================
# Login
# ============================

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
        verify_password("dummy", "$argon2id$v=19$m=65536,t=3,p=4$dummy$dummy")
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

    # Successful login
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.now(timezone.utc)

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)

    access_token, expires_at = create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role.value,
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
        role=user.role.value,
        username=user.username,
    )


# ============================
# Refresh
# ============================

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

    if db_token.expires_at < datetime.now(timezone.utc):
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

    access_token, expires_at = create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role.value,
    )

    await db.commit()

    return TokenResponse(access_token=access_token, expires_at=expires_at)


# ============================
# Logout
# ============================

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


# ============================
# Admin Bootstrap (Race Safe)
# ============================

async def ensure_admin_exists(db: AsyncSession):
    from config import get_settings
    settings = get_settings()

    result = await db.execute(
        select(User).where(User.username == settings.INITIAL_ADMIN_USERNAME)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return

    admin_password = settings.INITIAL_ADMIN_PASSWORD
    if not admin_password:
        import secrets
        admin_password = secrets.token_urlsafe(16)
        logger.warning(
            "generated_admin_password",
            password=admin_password,
        )

    admin = User(
        username=settings.INITIAL_ADMIN_USERNAME,
        password_hash=hash_password(admin_password),
        role=UserRole.ADMIN.value,
        is_active=True,
    )

    try:
        db.add(admin)
        await db.commit()
        logger.info("admin_user_created", username=settings.INITIAL_ADMIN_USERNAME)
    except IntegrityError:
        await db.rollback()
        logger.info("admin_already_exists", username=settings.INITIAL_ADMIN_USERNAME)
