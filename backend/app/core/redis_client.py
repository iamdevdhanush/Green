"""
GreenOps Redis Client
Caching and pub/sub for real-time updates.
"""
import json
from typing import Any, Optional

import redis

from app.core.config import settings

_pool = redis.ConnectionPool.from_url(settings.REDIS_URL, decode_responses=True)


def get_redis() -> redis.Redis:
    return redis.Redis(connection_pool=_pool)


class CacheManager:
    def __init__(self):
        self._r = get_redis()

    def get(self, key: str) -> Optional[Any]:
        val = self._r.get(key)
        if val is None:
            return None
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        self._r.setex(key, ttl, json.dumps(value, default=str))

    def delete(self, key: str) -> None:
        self._r.delete(key)

    def delete_pattern(self, pattern: str) -> None:
        keys = self._r.keys(pattern)
        if keys:
            self._r.delete(*keys)

    def publish(self, channel: str, message: Any) -> None:
        self._r.publish(channel, json.dumps(message, default=str))


cache = CacheManager()
