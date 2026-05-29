from __future__ import annotations

import time

from redis.exceptions import RedisError
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.middleware import RateLimitMiddleware
from app.services import rate_limit
from app.services.rate_limit import RedisRateLimiter


class FakePipeline:
    def __init__(self, client):
        self.client = client
        self.commands = []

    def incr(self, key):
        self.commands.append(("incr", key))
        return self

    def expire(self, key, seconds, nx=False):
        self.commands.append(("expire", key, seconds, nx))
        return self

    def execute(self):
        results = []
        for command in self.commands:
            if command[0] == "incr":
                results.append(self.client.incr(command[1]))
            elif command[0] == "expire":
                _, key, seconds, nx = command
                results.append(self.client.expire(key, seconds, nx=nx))
        return results


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.expires_at = {}
        self.now = time.monotonic()

    def pipeline(self, transaction=True):
        assert transaction is True
        return FakePipeline(self)

    def incr(self, key):
        self._expire_old_keys()
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    def expire(self, key, seconds, nx=False):
        if nx and key in self.expires_at:
            return False
        self.expires_at[key] = self.now + seconds
        return True

    def advance(self, seconds):
        self.now += seconds
        self._expire_old_keys()

    def _expire_old_keys(self):
        expired = [key for key, expires_at in self.expires_at.items() if expires_at <= self.now]
        for key in expired:
            self.values.pop(key, None)
            self.expires_at.pop(key, None)


class FailingRedis:
    def pipeline(self, transaction=True):
        raise RedisError("redis unavailable")


def limiter_with(client) -> RedisRateLimiter:
    limiter = RedisRateLimiter("redis://test")
    limiter._client = client
    return limiter


def test_rate_limit_counter_increments_and_exceeds_limit():
    limiter = limiter_with(FakeRedis())
    key = "rate_limit:ip:127.0.0.1"

    first = limiter.check(key, limit=2, window_seconds=60)
    second = limiter.check(key, limit=2, window_seconds=60)
    third = limiter.check(key, limit=2, window_seconds=60)

    assert first.allowed is True
    assert first.count == 1
    assert second.allowed is True
    assert second.count == 2
    assert third.allowed is False
    assert third.count == 3


def test_rate_limit_ttl_expiration_resets_counter():
    redis = FakeRedis()
    limiter = limiter_with(redis)
    key = "rate_limit:ip:127.0.0.1"

    assert limiter.check(key, limit=1, window_seconds=60).allowed is True
    assert limiter.check(key, limit=1, window_seconds=60).allowed is False
    redis.advance(61)

    result = limiter.check(key, limit=1, window_seconds=60)

    assert result.allowed is True
    assert result.count == 1


def test_multiple_limiters_share_same_redis_state():
    redis = FakeRedis()
    first_limiter = limiter_with(redis)
    second_limiter = limiter_with(redis)
    key = "rate_limit:ip:127.0.0.1"

    assert first_limiter.check(key, limit=1, window_seconds=60).allowed is True
    result = second_limiter.check(key, limit=1, window_seconds=60)

    assert result.allowed is False
    assert result.count == 2


def test_rate_limit_uses_namespaced_ip_keys():
    assert RedisRateLimiter.ip_key("1.2.3.4") == "rate_limit:ip:1.2.3.4"


def test_redis_failure_fails_open_without_crashing():
    limiter = limiter_with(FailingRedis())

    result = limiter.check("rate_limit:ip:127.0.0.1", limit=1, window_seconds=60)

    assert result.allowed is True
    assert result.count == 0


def test_middleware_returns_existing_429_response_when_limit_exceeded(monkeypatch):
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

    @app.get("/limited")
    def limited():
        return {"ok": True}

    monkeypatch.setattr(
        rate_limit.rate_limiter,
        "check_ip",
        lambda ip_address, limit, window_seconds: rate_limit.RateLimitResult(
            allowed=False,
            count=limit + 1,
            limit=limit,
            key=RedisRateLimiter.ip_key(ip_address),
        ),
    )

    response = TestClient(app).get("/limited")

    assert response.status_code == 429
    assert response.json() == {"detail": "Rate limit exceeded"}
