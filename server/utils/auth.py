"""
GreenOps Authentication Utilities
- Argon2id password hashing
- JWT access + refresh tokens
- Agent token generation
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import jwt
import structlog
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

from config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

# Argon2id password hasher - OWASP recommended parameters
_ph = PasswordHasher(
    time_cost=3,        # Number of iterations
    memory_cost=65536,  # 64 MiB
    parallelism=4,      # 4 parallel threads
    hash_len=32,        # 32 byte hash
    salt_len=16,        # 16 byte salt
)


def hash_password(password: str) -> str:
    """Hash password using Argon2id."""
    return _ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against Argon2id hash."""
    try:
        return _ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(hashed_password: str) -> bool:
    """Check if password hash needs upgrading."""
    return _ph.check_needs_rehash(hashed_password)


def create_access_token(
    user_id: int,
    username: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> Tuple[str, datetime]:
    """Create JWT access token. Returns (token, expiry)."""
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    expire = datetime.now(timezone.utc) + expires_delta
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "type": "access",
        "iat": datetime.now(timezone.utc),
        "exp": expire,
        "jti": str(uuid.uuid4()),
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, expire


def create_refresh_token() -> Tuple[str, str, datetime]:
    """Create refresh token. Returns (raw_token, token_hash, expiry)."""
    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return raw_token, token_hash, expire


def hash_refresh_token(raw_token: str) -> str:
    """Hash a refresh token for storage."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and validate JWT access token.
    Returns payload dict or None if invalid.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_exp": True},
        )
        if payload.get("type") != "access":
            return None
        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("token_expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.debug("token_invalid", error=str(e))
        return None


def generate_agent_token() -> Tuple[str, str]:
    """Generate agent token. Returns (raw_token, token_hash)."""
    raw_token = f"agt_{secrets.token_urlsafe(32)}"
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    return raw_token, token_hash


def hash_agent_token(raw_token: str) -> str:
    """Hash an agent token for storage/lookup."""
    return hashlib.sha256(raw_token.encode()).hexdigest()
