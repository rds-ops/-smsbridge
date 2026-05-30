from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from sqlalchemy import text

from app.api.admin import router as admin_router
from app.api.api_v1 import router as api_v1_router
from app.api.auth import router as auth_router
from app.api.internal_provider_webhooks import router as internal_provider_webhooks_router
from app.api.supplier import router as supplier_router
from app.core.config import settings, validate_production_safety
from app.core.middleware import ApiRequestLogMiddleware, RateLimitMiddleware
from app.db.session import engine

validate_production_safety(settings)

app = FastAPI(
    title="smsbridge API",
    description="Compliant SMS verification testing API for developers, QA teams and international onboarding checks.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ApiRequestLogMiddleware)
app.add_middleware(RateLimitMiddleware)

app.include_router(auth_router)
app.include_router(api_v1_router)
app.include_router(admin_router)
app.include_router(supplier_router)
app.include_router(internal_provider_webhooks_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.app_name}


@app.get("/health/live")
def health_live():
    return {"status": "ok"}


@app.get("/health/ready")
def health_ready():
    # Keep this cheap and safe: short checks, no secrets, no stack traces.
    checks: dict[str, str] = {}
    ok = True

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        ok = False
        checks["database"] = "error"

    # Redis is a critical dependency in production, but unit tests may run without it.
    if settings.redis_url and settings.environment.strip().lower() not in {"test"}:
        try:
            import redis  # local import to keep dependency surface minimal

            client = redis.Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=0.25,
                socket_timeout=0.25,
            )
            client.ping()
            checks["redis"] = "ok"
        except Exception:
            ok = False
            checks["redis"] = "error"
    else:
        checks["redis"] = "skipped"

    if not ok:
        return JSONResponse({"status": "not_ready", "checks": checks}, status_code=503)
    return {"status": "ready", "checks": checks}
