from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.api.internal_provider_webhooks import require_internal_webhook_secret
from app.db.session import get_db
from app.services.payment_intents import process_payment_webhook

router = APIRouter(prefix="/internal/payment-webhooks", tags=["internal-payment-webhooks"])


@router.post("/{provider}")
def payment_webhook(
    provider: str,
    payload: dict,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    _: None = Depends(require_internal_webhook_secret),
):
    event, intent = process_payment_webhook(
        db,
        provider=provider,
        payload=payload,
        idempotency_key=idempotency_key,
    )
    db.commit()
    return {
        "status": event.status,
        "provider": event.provider,
        "payment_intent_public_id": intent.public_id if intent else None,
    }

