"""
GreenOps Authentication Utilities
===================================
Pure utility functions for password hashing, JWT creation/decoding,
refresh token management, and agent token management.

This module has NO FastAPI router. It is imported by:
  - server/routers/auth.py   (login, refresh, logout, verify, me endpoints)
  - server/routers/agents.py (generate_agent_token, hash_agent_token)
  - server/utils/security.py (decode_access_token, hash_agent_token)
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import jwt
import structlog
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# Password hasher — single module-level instance used for BOTH hash() and
# verify(). Parameters must never change once hashes are stored in production,
# because the argon2 encoded string embeds them and verify() reads them from
# the stored hash — but we keep a consistent instance to catch config drift.
#
#   time_cost=3       — 3 iterations over memory
#   memory_cost=65536 — 64 MB per hash (memory-hard)
#   parallelism=4     — 4 threads
#   hash_len=32       — 32-byte output digest
#   salt_len=16       — 16-byte random salt (embedded in the hash string)
# ---------------------------------------------------------------------------
_ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

# ---------------------------------------------------------------------------
# Pre-compute a VALID Argon2id dummy hash at module load time.
#
# WHY THIS MATTERS:
#   A hardcoded invalid hash string causes argon2-cffi to raise
#   InvalidHashError immediately (microseconds), allowing timing attacks
#   to enumerate valid usernames. A real hash forces full memory-hard
#   computation (~100 ms) before returning False — matching a real failed
#   login attempt.
# ---------------------------------------------------------------------------
_DUMMY_HASH: str = _ph.hash("__greenops_timing_dummy_do_not_use__")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Hash a plaintext password with Argon2id. Returns the full encoded string."""
    return _ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plaintext password against a stored Argon2id hash.

    Never raises — always returns bool. Safe to call directly in if-statements.
    """
    try:
        return _ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(hashed_password: str) -> bool:
    """
    Return True if the stored hash was created with different PasswordHasher
    parameters than the current _ph and should be silently upgraded on next
    successful login.
    """
    try:
        return _ph.check_needs_rehash(hashed_password)
    except InvalidHashError:
        # Malformed hash in DB — treat as stale so it gets replaced.
        return True


def timing_safe_dummy_verify() -> None:
    """
    Execute a full Argon2 memory-hard verification against the module-level
    dummy hash. Consumes the same ~100 ms as a real failed login.

    Call this in every code path that rejects a login WITHOUT checking a real
    password (e.g. user not found, account disabled, account locked). Without
    this call, those paths return in <1 ms, leaking username validity.
    """
    # Always False — we never pass the matching input. The point is CPU time.
    verify_password("__greenops_timing_dummy_input__", _DUMMY_HASH)


def create_access_token(
    user_id: int,
    username: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> Tuple[str, datetime]:
    """Create a signed JWT access token. Returns (token, expires_at)."""
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
    """Return (raw_token, sha256_hex_hash, expires_at)."""
    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return raw_token, token_hash, expire


def hash_refresh_token(raw_token: str) -> str:
    """Return SHA-256 hex digest of a refresh token."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and validate a JWT access token.
    Returns the payload dict on success, None on any failure.
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
        return None
    except jwt.InvalidTokenError:
        return None


def generate_agent_token() -> Tuple[str, str]:
    """
    Generate a new agent bearer token.
    Returns (raw_token, sha256_hex_hash).
    Raw token is prefixed with 'agt_' for easy identification in logs.
    """
    raw_token = f"agt_{secrets.token_urlsafe(32)}"
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    return raw_token, token_hash


def hash_agent_token(raw_token: str) -> str:
    """Return SHA-256 hex digest of an agent token."""
    return hashlib.sha256(raw_token.encode()).hexdigest()
