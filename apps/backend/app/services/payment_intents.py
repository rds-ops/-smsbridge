from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import PaymentIntent, PaymentWebhookEvent, User

PAYMENT_INTENT_EXPIRY_MINUTES = 30
ALLOWED_PAYMENT_PROVIDERS = {"manual_test", "payme", "click", "crypto_usdt"}
ENABLED_PAYMENT_PROVIDERS = {"manual_test"}
PAYMENT_WEBHOOK_TARGET_STATUSES = {"pending", "succeeded", "failed", "cancelled"}
PAYMENT_INTENT_TRANSITIONS = {
    "created": {"pending", "failed", "cancelled"},
    "pending": {"succeeded", "failed", "cancelled"},
}


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


def payment_webhook_payload_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def process_payment_webhook(
    db: Session,
    *,
    provider: str,
    payload: dict[str, Any],
    idempotency_key: str | None = None,
) -> tuple[PaymentWebhookEvent, PaymentIntent | None]:
    provider_normalized = provider.strip().lower()
    if provider_normalized not in ALLOWED_PAYMENT_PROVIDERS:
        raise HTTPException(status_code=400, detail="Unsupported payment provider")

    external_event_id = _string_or_none(
        payload.get("external_event_id") or payload.get("event_id") or payload.get("id")
    )
    key = (idempotency_key or "").strip() or None
    payload_hash = payment_webhook_payload_hash(payload)

    existing = _existing_webhook_event(
        db,
        provider=provider_normalized,
        external_event_id=external_event_id,
        payload_hash=payload_hash,
    )
    if existing:
        return PaymentWebhookEvent(
            provider=provider_normalized,
            external_event_id=external_event_id,
            idempotency_key=key,
            payload_hash=payload_hash,
            status="duplicate",
        ), None

    intent = _find_payment_intent(db, provider=provider_normalized, payload=payload)
    target_status = _string_or_none(payload.get("status"))
    event_status = "ignored"

    if intent and target_status in PAYMENT_WEBHOOK_TARGET_STATUSES and _can_transition(intent.status, target_status):
        _transition_payment_intent(intent, target_status)
        event_status = "processed"

    event = PaymentWebhookEvent(
        provider=provider_normalized,
        external_event_id=external_event_id,
        idempotency_key=key,
        payload_hash=payload_hash,
        status=event_status,
    )
    db.add(event)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return PaymentWebhookEvent(
            provider=provider_normalized,
            external_event_id=external_event_id,
            idempotency_key=key,
            payload_hash=payload_hash,
            status="duplicate",
        ), None
    return event, intent


def _existing_webhook_event(
    db: Session,
    *,
    provider: str,
    external_event_id: str | None,
    payload_hash: str,
) -> PaymentWebhookEvent | None:
    if external_event_id:
        existing = db.scalar(
            select(PaymentWebhookEvent).where(
                PaymentWebhookEvent.provider == provider,
                PaymentWebhookEvent.external_event_id == external_event_id,
            )
        )
        if existing:
            return existing
    return db.scalar(
        select(PaymentWebhookEvent).where(
            PaymentWebhookEvent.provider == provider,
            PaymentWebhookEvent.payload_hash == payload_hash,
        )
    )


def _find_payment_intent(db: Session, *, provider: str, payload: dict[str, Any]) -> PaymentIntent | None:
    public_id = _string_or_none(payload.get("payment_intent_public_id") or payload.get("public_id"))
    if public_id:
        return db.scalar(
            select(PaymentIntent).where(PaymentIntent.provider == provider, PaymentIntent.public_id == public_id)
        )

    provider_reference = _string_or_none(payload.get("provider_reference"))
    if provider_reference:
        return db.scalar(
            select(PaymentIntent).where(
                PaymentIntent.provider == provider,
                PaymentIntent.provider_reference == provider_reference,
            )
        )
    return None


def _can_transition(current: str, target: str) -> bool:
    return target in PAYMENT_INTENT_TRANSITIONS.get(current, set())


def _transition_payment_intent(intent: PaymentIntent, target_status: str) -> None:
    now = datetime.now(timezone.utc)
    intent.status = target_status
    if target_status == "succeeded":
        intent.succeeded_at = now
    elif target_status == "failed":
        intent.failed_at = now
    elif target_status == "cancelled":
        intent.cancelled_at = now


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
