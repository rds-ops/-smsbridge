from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.api_v1 import router as api_v1_router
from app.api.auth import router as auth_router
from app.api.supplier import router as supplier_router
from app.core.config import settings, validate_production_safety
from app.core.middleware import ApiRequestLogMiddleware, RateLimitMiddleware

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


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.app_name}
