from __future__ import annotations

from fastapi import Request
from starlette.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import select

from app.core.config import settings
from app.core.security import decode_token, hash_api_key
from app.db.session import SessionLocal
from app.models import ApiRequestLog, BuyerApiKey, Supplier, User
from app.services.rate_limit import rate_limiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/health"):
            return await call_next(request)
        ip_address = request.client.host if request.client else "unknown"
        key = self._identity_key(request, ip_address)
        result = rate_limiter.check(key, settings.rate_limit_per_minute, 60)
        if not result.allowed:
            return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
        return await call_next(request)

    @staticmethod
    def _identity_key(request: Request, ip_address: str) -> str:
        fallback = rate_limiter.ip_key(ip_address)
        authorization = request.headers.get("authorization")
        if not authorization:
            return fallback
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return fallback

        payload = decode_token(token)
        if payload and payload.get("typ") == "access":
            try:
                return rate_limiter.user_key(int(payload["sub"]))
            except (KeyError, TypeError, ValueError):
                return fallback

        token_hash = hash_api_key(token)
        db = SessionLocal()
        try:
            managed_key = db.scalar(
                select(BuyerApiKey.id).where(
                    BuyerApiKey.key_hash == token_hash,
                    BuyerApiKey.status == "active",
                )
            )
            if managed_key is not None:
                return rate_limiter.buyer_api_key_key(int(managed_key))

            legacy_user_id = db.scalar(select(User.id).where(User.api_key_hash == token_hash))
            if legacy_user_id is not None:
                return rate_limiter.user_key(int(legacy_user_id))

            supplier_id = db.scalar(select(Supplier.id).where(Supplier.api_key_hash == token_hash))
            if supplier_id is not None:
                return rate_limiter.supplier_key(int(supplier_id))
        finally:
            db.close()
        return fallback


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
