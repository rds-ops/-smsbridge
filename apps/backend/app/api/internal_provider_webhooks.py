from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models import Provider

router = APIRouter(prefix="/internal/provider-webhooks", tags=["internal-provider-webhooks"])


def require_internal_webhook_secret(
    x_internal_webhook_secret: str | None = Header(default=None, alias="X-Internal-Webhook-Secret"),
) -> None:
    secret = (x_internal_webhook_secret or "").strip()
    if not secret:
        raise HTTPException(status_code=403, detail="Forbidden")
    if secret != settings.internal_webhook_secret:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.post("/{provider_code}")
def provider_webhook_placeholder(
    provider_code: str,
    payload: dict,
    db: Session = Depends(get_db),
    _: None = Depends(require_internal_webhook_secret),
):
    provider = db.scalar(select(Provider).where(Provider.code == provider_code))
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    if provider.status != "active":
        raise HTTPException(status_code=409, detail="Provider is not active")

    # Intentionally behavior-preserving placeholder:
    # - do not mutate orders yet
    # - do not store request payload
    _ = payload
    return {"status": "accepted", "provider_code": provider.code, "detail": "not_implemented"}

