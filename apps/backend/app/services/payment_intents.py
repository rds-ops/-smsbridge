from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import PaymentIntent, User

PAYMENT_INTENT_EXPIRY_MINUTES = 30
ALLOWED_PAYMENT_PROVIDERS = {"manual_test", "payme", "click", "crypto_usdt"}
ENABLED_PAYMENT_PROVIDERS = {"manual_test"}


def payment_intent_request_hash(*, amount: Decimal, provider: str, currency: str) -> str:
    payload = {
        "amount": str(amount.quantize(Decimal("0.0001"))),
        "provider": provider,
        "currency": currency.upper(),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def create_payment_intent(
    db: Session,
    *,
    user: User,
    amount: Decimal,
    provider: str,
    currency: str | None,
    idempotency_key: str | None,
) -> PaymentIntent:
    provider_normalized = provider.strip().lower()
    if provider_normalized not in ALLOWED_PAYMENT_PROVIDERS:
        raise HTTPException(status_code=400, detail="Unsupported payment provider")
    if provider_normalized not in ENABLED_PAYMENT_PROVIDERS:
        raise HTTPException(status_code=400, detail="Payment provider is not enabled")

    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    currency_normalized = (currency or user.wallet.currency or "USD").strip().upper()
    if len(currency_normalized) != 3:
        raise HTTPException(status_code=400, detail="Currency must be a 3-letter code")

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=PAYMENT_INTENT_EXPIRY_MINUTES)
    key = (idempotency_key or "").strip() or None
    if key and len(key) > 255:
        raise HTTPException(status_code=400, detail="Idempotency-Key is too long")

    req_hash = payment_intent_request_hash(amount=amount, provider=provider_normalized, currency=currency_normalized)
    intent = PaymentIntent(
        user_id=user.id,
        provider=provider_normalized,
        currency=currency_normalized,
        amount=amount.quantize(Decimal("0.0001")),
        status="created",
        idempotency_key=key,
        request_hash=req_hash if key else None,
        intent_metadata={},
        expires_at=expires_at,
    )

    if not key:
        db.add(intent)
        db.flush()
        return intent

    db.add(intent)
    try:
        db.flush()
        return intent
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(PaymentIntent).where(
                PaymentIntent.user_id == user.id,
                PaymentIntent.idempotency_key == key,
            )
        )
        if not existing:
            raise
        if existing.request_hash != req_hash:
            raise HTTPException(status_code=409, detail="Idempotency-Key was already used with a different request")
        return existing


def get_user_payment_intent(db: Session, *, user: User, public_id: str) -> PaymentIntent:
    intent = db.scalar(select(PaymentIntent).where(PaymentIntent.public_id == public_id, PaymentIntent.user_id == user.id))
    if not intent:
        raise HTTPException(status_code=404, detail="Payment intent not found")
    return intent

