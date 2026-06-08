from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request
from starlette.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import select

from app.core.config import settings
from app.core.security import decode_token, hash_api_key
from app.db.session import SessionLocal
from app.models import ApiRequestLog, BuyerApiKey, Supplier, User
from app.services.rate_limit import rate_limiter


@dataclass(frozen=True)
class RateLimitPolicy:
    key: str
    limit: int


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/health"):
            return await call_next(request)
        ip_address = request.client.host if request.client else "unknown"
        policy = self._policy(request, ip_address)
        result = rate_limiter.check(policy.key, policy.limit, 60)
        if not result.allowed:
            return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
        return await call_next(request)

    @staticmethod
    def _limit(value: int | None, fallback: int) -> int:
        return int(value if value is not None else fallback)

    @classmethod
    def _user_limit(cls, user: User) -> int:
        if user.role == "admin":
            return cls._limit(settings.rate_limit_admin_per_minute, max(settings.rate_limit_per_minute, 1000))
        tier = (user.tier or "default").strip().lower()
        if tier == "verified":
            return cls._limit(settings.rate_limit_user_verified_per_minute, settings.rate_limit_per_minute * 2)
        if tier == "wholesale":
            return cls._limit(settings.rate_limit_user_wholesale_per_minute, settings.rate_limit_per_minute * 5)
        if tier == "partner":
            return cls._limit(settings.rate_limit_user_partner_per_minute, settings.rate_limit_per_minute * 10)
        return cls._limit(settings.rate_limit_user_default_per_minute, settings.rate_limit_per_minute)

    @classmethod
    def _policy(cls, request: Request, ip_address: str) -> RateLimitPolicy:
        fallback = rate_limiter.ip_key(ip_address)
        anonymous_limit = cls._limit(settings.rate_limit_anonymous_per_minute, settings.rate_limit_per_minute)
        authorization = request.headers.get("authorization")
        if not authorization:
            return RateLimitPolicy(fallback, anonymous_limit)
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return RateLimitPolicy(fallback, anonymous_limit)

        payload = decode_token(token)
        if payload and payload.get("typ") == "access":
            try:
                user_id = int(payload["sub"])
            except (KeyError, TypeError, ValueError):
                return RateLimitPolicy(fallback, anonymous_limit)
            db = SessionLocal()
            try:
                user = db.get(User, user_id)
                if user:
                    return RateLimitPolicy(rate_limiter.user_key(user.id), cls._user_limit(user))
            finally:
                db.close()
            return RateLimitPolicy(fallback, anonymous_limit)

        token_hash = hash_api_key(token)
        db = SessionLocal()
        try:
            managed_key = db.execute(
                select(BuyerApiKey.id, User)
                .join(User, User.id == BuyerApiKey.user_id)
                .where(
                    BuyerApiKey.key_hash == token_hash,
                    BuyerApiKey.status == "active",
                )
            ).first()
            if managed_key is not None:
                key_id, user = managed_key
                return RateLimitPolicy(rate_limiter.buyer_api_key_key(int(key_id)), cls._user_limit(user))

            legacy_user = db.scalar(select(User).where(User.api_key_hash == token_hash))
            if legacy_user is not None:
                return RateLimitPolicy(rate_limiter.user_key(legacy_user.id), cls._user_limit(legacy_user))

            supplier_id = db.scalar(select(Supplier.id).where(Supplier.api_key_hash == token_hash))
            if supplier_id is not None:
                return RateLimitPolicy(
                    rate_limiter.supplier_key(int(supplier_id)),
                    cls._limit(settings.rate_limit_supplier_per_minute, settings.rate_limit_per_minute),
                )
        finally:
            db.close()
        return RateLimitPolicy(fallback, anonymous_limit)


class ApiRequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith(
            ("/api/", "/admin", "/auth", "/supplier/v1", "/internal/provider-webhooks", "/internal/payment-webhooks")
        ):
            db = SessionLocal()
            try:
                db.add(
                    ApiRequestLog(
                        user_id=getattr(request.state, "user_id", None),
                        supplier_id=getattr(request.state, "supplier_id", None),
                        buyer_api_key_id=getattr(request.state, "buyer_api_key_id", None),
                        endpoint=request.url.path,
                        method=request.method,
                        ip_address=request.client.host if request.client else None,
                        status_code=response.status_code,
                    )
                )
                db.commit()
            finally:
                db.close()
        return response
