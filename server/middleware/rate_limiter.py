"""
GreenOps Rate Limiting Middleware
In-memory rate limiter with per-IP and per-endpoint limits.
For production at scale, replace with Redis-backed implementation.
"""
import time
from collections import defaultdict
from threading import Lock
from typing import Dict, Tuple

import structlog
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class TokenBucket:
    """Thread-safe token bucket rate limiter."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: Dict[str, Tuple[int, float]] = {}
        self._lock = Lock()

    def is_allowed(self, key: str) -> Tuple[bool, int, int]:
        """
        Check if request is allowed.
        Returns (allowed, remaining, retry_after).
        """
        with self._lock:
            now = time.time()
            if key in self._buckets:
                count, window_start = self._buckets[key]
                if now - window_start > self.window_seconds:
                    # Reset window
                    self._buckets[key] = (1, now)
                    return True, self.max_requests - 1, 0
                elif count >= self.max_requests:
                    retry_after = int(self.window_seconds - (now - window_start)) + 1
                    return False, 0, retry_after
                else:
                    self._buckets[key] = (count + 1, window_start)
                    remaining = self.max_requests - count - 1
                    return True, remaining, 0
            else:
                self._buckets[key] = (1, now)
                return True, self.max_requests - 1, 0

    def cleanup_old_entries(self):
        """Remove expired entries to prevent memory leak."""
        with self._lock:
            now = time.time()
            expired_keys = [
                k for k, (_, window_start) in self._buckets.items()
                if now - window_start > self.window_seconds * 2
            ]
            for k in expired_keys:
                del self._buckets[k]


# Global rate limiters
_general_limiter = TokenBucket(
    settings.RATE_LIMIT_REQUESTS,
    settings.RATE_LIMIT_WINDOW_SECONDS,
)
_login_limiter = TokenBucket(
    settings.LOGIN_RATE_LIMIT_REQUESTS,
    settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
)

_cleanup_counter = 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware."""

    async def dispatch(self, request: Request, call_next):
        global _cleanup_counter

        # Get client IP (respects X-Forwarded-For from trusted proxies)
        client_ip = self._get_client_ip(request)

        # Periodic cleanup
        _cleanup_counter += 1
        if _cleanup_counter % 1000 == 0:
            _general_limiter.cleanup_old_entries()
            _login_limiter.cleanup_old_entries()

        # Login endpoint gets stricter limits
        path = request.url.path
        if path == "/api/auth/login" and request.method == "POST":
            allowed, remaining, retry_after = _login_limiter.is_allowed(client_ip)
            if not allowed:
                logger.warning(
                    "login_rate_limit_exceeded",
                    client_ip=client_ip,
                    retry_after=retry_after,
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "rate_limit_exceeded",
                        "message": "Too many login attempts. Please try again later.",
                        "retry_after": retry_after,
                    },
                    headers={"Retry-After": str(retry_after)},
                )

        # General rate limit
        allowed, remaining, retry_after = _general_limiter.is_allowed(client_ip)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "message": "Too many requests.",
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response

    def _get_client_ip(self, request: Request) -> str:
        """Get real client IP, handling reverse proxy headers."""
        # Trust X-Forwarded-For only if behind known proxy
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP (original client)
            return forwarded_for.split(",")[0].strip()
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        if request.client:
            return request.client.host
        return "unknown"
