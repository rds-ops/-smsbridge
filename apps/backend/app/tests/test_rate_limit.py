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
    assert RedisRateLimiter.user_key(123) == "rate_limit:user:123"
    assert RedisRateLimiter.buyer_api_key_key(456) == "rate_limit:buyer_api_key:456"
    assert RedisRateLimiter.supplier_key(789) == "rate_limit:supplier:789"


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
        "check",
        lambda key, limit, window_seconds: rate_limit.RateLimitResult(
            allowed=False,
            count=limit + 1,
            limit=limit,
            key=key,
        ),
    )

    response = TestClient(app).get("/limited")

    assert response.status_code == 429
    assert response.json() == {"detail": "Rate limit exceeded"}


def test_health_endpoints_bypass_rate_limit(monkeypatch):
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

    @app.get("/health/live")
    def health_live():
        return {"status": "ok"}

    def fail_if_called(key, limit, window_seconds):
        raise AssertionError("health endpoint should not call rate limiter")

    monkeypatch.setattr(rate_limit.rate_limiter, "check", fail_if_called)

    response = TestClient(app).get("/health/live")

    assert response.status_code == 200


def test_rate_limit_uses_managed_api_key_bucket(client, user_token, monkeypatch):
    seen: list[tuple[str, int]] = []

    def capture(key, limit, window_seconds):
        seen.append((key, limit))
        return rate_limit.RateLimitResult(allowed=True, count=1, limit=limit, key=key)

    monkeypatch.setattr(rate_limit.rate_limiter, "check", capture)
    created = client.post(
        "/api/v1/api-keys",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"name": "rate limit key", "scopes": ["wallet:read"]},
    )
    assert created.status_code == 200, created.text

    seen.clear()
    response = client.get("/api/v1/balance", headers={"Authorization": f"Bearer {created.json()['api_key']}"})
    assert response.status_code == 200, response.text

    from app.db.session import SessionLocal
    from app.models import BuyerApiKey
    from sqlalchemy import select

    with SessionLocal() as db:
        key_id = db.scalar(select(BuyerApiKey.id).where(BuyerApiKey.public_id == created.json()["public_id"]))
    assert seen[-1] == (RedisRateLimiter.buyer_api_key_key(key_id), rate_limit.settings.rate_limit_per_minute)


def test_different_managed_api_keys_have_separate_rate_buckets(client, user_token, monkeypatch):
    seen_keys: list[str] = []

    def capture(key, limit, window_seconds):
        seen_keys.append(key)
        return rate_limit.RateLimitResult(allowed=True, count=1, limit=limit, key=key)

    monkeypatch.setattr(rate_limit.rate_limiter, "check", capture)
    first = client.post(
        "/api/v1/api-keys",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"name": "first", "scopes": ["wallet:read"]},
    ).json()
    second = client.post(
        "/api/v1/api-keys",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"name": "second", "scopes": ["wallet:read"]},
    ).json()

    seen_keys.clear()
    assert client.get("/api/v1/balance", headers={"Authorization": f"Bearer {first['api_key']}"}).status_code == 200
    first_bucket = seen_keys[-1]
    assert client.get("/api/v1/balance", headers={"Authorization": f"Bearer {second['api_key']}"}).status_code == 200
    second_bucket = seen_keys[-1]

    assert first_bucket.startswith("rate_limit:buyer_api_key:")
    assert second_bucket.startswith("rate_limit:buyer_api_key:")
    assert first_bucket != second_bucket


def test_rate_limit_uses_jwt_user_bucket(client, user_token, monkeypatch):
    seen: list[tuple[str, int]] = []

    def capture(key, limit, window_seconds):
        seen.append((key, limit))
        return rate_limit.RateLimitResult(allowed=True, count=1, limit=limit, key=key)

    monkeypatch.setattr(rate_limit.rate_limiter, "check", capture)

    response = client.get("/api/v1/balance", headers={"Authorization": f"Bearer {user_token}"})

    assert response.status_code == 200, response.text
    assert seen[-1] == (RedisRateLimiter.user_key(2), rate_limit.settings.rate_limit_per_minute)


def test_rate_limit_uses_ip_bucket_for_unauthenticated_requests(client, monkeypatch):
    seen: list[tuple[str, int]] = []

    def capture(key, limit, window_seconds):
        seen.append((key, limit))
        return rate_limit.RateLimitResult(allowed=True, count=1, limit=limit, key=key)

    monkeypatch.setattr(rate_limit.rate_limiter, "check", capture)

    response = client.post("/auth/login", json={"email": "missing@example.com", "password": "bad"})

    assert response.status_code == 401
    key, limit = seen[-1]
    assert key.startswith("rate_limit:ip:")
    assert limit == rate_limit.settings.rate_limit_per_minute


def test_anonymous_uses_configured_anonymous_limit(client, monkeypatch):
    seen: list[tuple[str, int]] = []

    def capture(key, limit, window_seconds):
        seen.append((key, limit))
        return rate_limit.RateLimitResult(allowed=True, count=1, limit=limit, key=key)

    monkeypatch.setattr(rate_limit.rate_limiter, "check", capture)
    monkeypatch.setattr("app.core.middleware.settings.rate_limit_anonymous_per_minute", 7)

    response = client.post("/auth/login", json={"email": "missing@example.com", "password": "bad"})

    assert response.status_code == 401
    assert seen[-1][1] == 7


def test_default_user_uses_configured_default_user_limit(client, user_token, monkeypatch):
    seen: list[tuple[str, int]] = []

    def capture(key, limit, window_seconds):
        seen.append((key, limit))
        return rate_limit.RateLimitResult(allowed=True, count=1, limit=limit, key=key)

    monkeypatch.setattr(rate_limit.rate_limiter, "check", capture)
    monkeypatch.setattr("app.core.middleware.settings.rate_limit_user_default_per_minute", 11)

    response = client.get("/api/v1/balance", headers={"Authorization": f"Bearer {user_token}"})

    assert response.status_code == 200, response.text
    assert seen[-1] == (RedisRateLimiter.user_key(2), 11)


def test_wholesale_and_partner_users_use_higher_tier_limits(client, admin_token, user_token, monkeypatch):
    seen: list[tuple[str, int]] = []

    def capture(key, limit, window_seconds):
        seen.append((key, limit))
        return rate_limit.RateLimitResult(allowed=True, count=1, limit=limit, key=key)

    monkeypatch.setattr(rate_limit.rate_limiter, "check", capture)
    monkeypatch.setattr("app.core.middleware.settings.rate_limit_user_wholesale_per_minute", 55)
    monkeypatch.setattr("app.core.middleware.settings.rate_limit_user_partner_per_minute", 77)

    patched = client.patch(
        "/admin/users/2/limits",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"tier": "wholesale"},
    )
    assert patched.status_code == 200, patched.text
    seen.clear()
    assert client.get("/api/v1/balance", headers={"Authorization": f"Bearer {user_token}"}).status_code == 200
    assert seen[-1] == (RedisRateLimiter.user_key(2), 55)

    patched = client.patch(
        "/admin/users/2/limits",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"tier": "partner"},
    )
    assert patched.status_code == 200, patched.text
    seen.clear()
    assert client.get("/api/v1/balance", headers={"Authorization": f"Bearer {user_token}"}).status_code == 200
    assert seen[-1] == (RedisRateLimiter.user_key(2), 77)


def test_supplier_uses_configured_supplier_limit(client, admin_token, monkeypatch):
    seen: list[tuple[str, int]] = []

    def capture(key, limit, window_seconds):
        seen.append((key, limit))
        return rate_limit.RateLimitResult(allowed=True, count=1, limit=limit, key=key)

    monkeypatch.setattr(rate_limit.rate_limiter, "check", capture)
    monkeypatch.setattr("app.core.middleware.settings.rate_limit_supplier_per_minute", 33)
    created = client.post(
        "/admin/suppliers",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": "Rate Supplier", "email": "rate-supplier@example.com", "status": "active", "reward_percent": "70.00"},
    )
    assert created.status_code == 200, created.text
    key_response = client.post(
        f"/admin/suppliers/{created.json()['id']}/api-key/regenerate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert key_response.status_code == 200, key_response.text

    seen.clear()
    response = client.get("/supplier/v1/me", headers={"Authorization": f"Bearer {key_response.json()['api_key']}"})

    assert response.status_code == 200, response.text
    assert seen[-1] == (RedisRateLimiter.supplier_key(created.json()["id"]), 33)
