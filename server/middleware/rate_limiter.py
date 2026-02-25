"""GreenOps Rate Limiting Middleware"""
import time
from typing import Dict, Tuple
from threading import Lock
import structlog
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class TokenBucket:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: Dict[str, Tuple[int, float]] = {}
        self._lock = Lock()

    def is_allowed(self, key: str) -> Tuple[bool, int, int]:
        with self._lock:
            now = time.time()
            if key in self._buckets:
                count, window_start = self._buckets[key]
                if now - window_start > self.window_seconds:
                    self._buckets[key] = (1, now)
                    return True, self.max_requests - 1, 0
                elif count >= self.max_requests:
                    retry_after = int(self.window_seconds - (now - window_start)) + 1
                    return False, 0, retry_after
                else:
                    self._buckets[key] = (count + 1, window_start)
                    return True, self.max_requests - count - 1, 0
            else:
                self._buckets[key] = (1, now)
                return True, self.max_requests - 1, 0

    def cleanup_old_entries(self):
        with self._lock:
            now = time.time()
            expired = [k for k, (_, ws) in self._buckets.items() if now - ws > self.window_seconds * 2]
            for k in expired:
                del self._buckets[k]


_general_limiter = TokenBucket(settings.RATE_LIMIT_REQUESTS, settings.RATE_LIMIT_WINDOW_SECONDS)
_login_limiter = TokenBucket(settings.LOGIN_RATE_LIMIT_REQUESTS, settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS)
_cleanup_counter = 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        global _cleanup_counter
        client_ip = self._get_client_ip(request)
        _cleanup_counter += 1
        if _cleanup_counter % 1000 == 0:
            _general_limiter.cleanup_old_entries()
            _login_limiter.cleanup_old_entries()

        if request.url.path == "/api/auth/login" and request.method == "POST":
            allowed, remaining, retry_after = _login_limiter.is_allowed(client_ip)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={"error": "rate_limit_exceeded", "message": "Too many login attempts.", "retry_after": retry_after},
                    headers={"Retry-After": str(retry_after)},
                )

        allowed, remaining, retry_after = _general_limiter.is_allowed(client_ip)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"error": "rate_limit_exceeded", "message": "Too many requests.", "retry_after": retry_after},
                headers={"Retry-After": str(retry_after)},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response

    def _get_client_ip(self, request: Request) -> str:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        if request.client:
            return request.client.host
        return "unknown"
