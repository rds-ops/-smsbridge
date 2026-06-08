from __future__ import annotations

import logging
from dataclasses import dataclass

import redis
from redis.exceptions import RedisError

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    count: int
    limit: int
    key: str


class RedisRateLimiter:
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._client: redis.Redis | None = None

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.Redis.from_url(self.redis_url, decode_responses=True)
        return self._client

    @staticmethod
    def ip_key(ip_address: str) -> str:
        return f"rate_limit:ip:{ip_address}"

    @staticmethod
    def user_key(user_id: int) -> str:
        return f"rate_limit:user:{user_id}"

    @staticmethod
    def buyer_api_key_key(api_key_id: int) -> str:
        return f"rate_limit:buyer_api_key:{api_key_id}"

    @staticmethod
    def supplier_key(supplier_id: int) -> str:
        return f"rate_limit:supplier:{supplier_id}"

    def check(self, key: str, limit: int, window_seconds: int = 60) -> RateLimitResult:
        try:
            pipe = self.client.pipeline(transaction=True)
            pipe.incr(key)
            pipe.expire(key, window_seconds, nx=True)
            count, _ = pipe.execute()
            count = int(count)
            return RateLimitResult(allowed=count <= limit, count=count, limit=limit, key=key)
        except RedisError:
            logger.exception("Redis rate limit check failed; failing open")
            return RateLimitResult(allowed=True, count=0, limit=limit, key=key)

    def check_ip(self, ip_address: str, limit: int, window_seconds: int = 60) -> RateLimitResult:
        return self.check(self.ip_key(ip_address), limit, window_seconds)


rate_limiter = RedisRateLimiter(settings.redis_url)
