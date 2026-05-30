from __future__ import annotations

from fastapi import Request
from starlette.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import ApiRequestLog
from app.services.rate_limit import rate_limiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        ip_address = request.client.host if request.client else "unknown"
        result = rate_limiter.check_ip(ip_address, settings.rate_limit_per_minute, 60)
        if not result.allowed:
            return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
        return await call_next(request)


class ApiRequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith(("/api/", "/admin", "/auth", "/supplier/v1", "/internal/provider-webhooks")):
            db = SessionLocal()
            try:
                db.add(
                    ApiRequestLog(
                        user_id=getattr(request.state, "user_id", None),
                        supplier_id=getattr(request.state, "supplier_id", None),
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
