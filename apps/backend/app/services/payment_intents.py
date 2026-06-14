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
import app.services.wallet as wallet

PAYMENT_INTENT_EXPIRY_MINUTES = 30
ALLOWED_PAYMENT_PROVIDERS = {"manual_test", "payme", "click", "crypto_usdt"}
ENABLED_PAYMENT_PROVIDERS = {"manual_test"}
PAYMENT_WEBHOOK_TARGET_STATUSES = {"pending", "succeeded", "failed", "cancelled"}
PAYMENT_INTENT_TRANSITIONS = {
    "created": {"pending", "failed", "cancelled"},
    "pending": {"succeeded", "failed", "cancelled"},
}
PAYMENT_WEBHOOK_ERROR_MESSAGES = {
    "invalid_status": "Unsupported payment webhook status",
    "invalid_transition": "Invalid payment intent status transition",
    "payment_intent_not_found": "Payment intent not found",
    "duplicate": "Duplicate payment webhook event",
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


def list_user_payment_intents(db: Session, *, user: User, limit: int, offset: int) -> list[PaymentIntent]:
    return list(
        db.scalars(
            select(PaymentIntent)
            .where(PaymentIntent.user_id == user.id)
            .order_by(PaymentIntent.created_at.desc(), PaymentIntent.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )


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
        _record_duplicate_webhook_attempt(
            db,
            provider=provider_normalized,
            payload=payload,
            external_event_id=external_event_id,
            idempotency_key=key,
        )
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
    event_error: str | None = None

    if intent and target_status in PAYMENT_WEBHOOK_TARGET_STATUSES and _can_transition(intent.status, target_status):
        _record_webhook_visibility(
            intent,
            external_event_id=external_event_id,
            idempotency_key=key,
            target_status=target_status,
            event_status="processed",
            event_error=None,
            payload=payload,
        )
        if target_status == "succeeded":
            wallet.deposit_payment_intent(db, intent)
        _transition_payment_intent(intent, target_status)
        event_status = "processed"
    elif intent:
        event_error = "invalid_status" if target_status not in PAYMENT_WEBHOOK_TARGET_STATUSES else "invalid_transition"
        _record_webhook_visibility(
            intent,
            external_event_id=external_event_id,
            idempotency_key=key,
            target_status=target_status,
            event_status="ignored",
            event_error=event_error,
            payload=payload,
        )
    else:
        event_error = "payment_intent_not_found"

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
        _record_duplicate_webhook_attempt(
            db,
            provider=provider_normalized,
            payload=payload,
            external_event_id=external_event_id,
            idempotency_key=key,
        )
        return PaymentWebhookEvent(
            provider=provider_normalized,
            external_event_id=external_event_id,
            idempotency_key=key,
            payload_hash=payload_hash,
            status="duplicate",
        ), None
    return event, intent


def manual_complete_payment_intent(db: Session, intent: PaymentIntent) -> PaymentIntent:
    if intent.provider != "manual_test":
        raise HTTPException(status_code=400, detail="Manual completion is only supported for manual_test payment intents")
    if intent.status == "succeeded":
        return intent
    if intent.status not in {"created", "pending"}:
        raise HTTPException(status_code=409, detail="Payment intent cannot be manually completed from its current status")

    if intent.status == "created":
        process_payment_webhook(
            db,
            provider="manual_test",
            payload={
                "event_id": f"manual-complete-{intent.public_id}-pending",
                "payment_intent_public_id": intent.public_id,
                "status": "pending",
            },
            idempotency_key=f"manual-complete-{intent.public_id}-pending",
        )

    process_payment_webhook(
        db,
        provider="manual_test",
        payload={
            "event_id": f"manual-complete-{intent.public_id}-succeeded",
            "payment_intent_public_id": intent.public_id,
            "status": "succeeded",
        },
        idempotency_key=f"manual-complete-{intent.public_id}-succeeded",
    )
    db.flush()
    return intent


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


def _record_duplicate_webhook_attempt(
    db: Session,
    *,
    provider: str,
    payload: dict[str, Any],
    external_event_id: str | None,
    idempotency_key: str | None,
) -> None:
    intent = _find_payment_intent(db, provider=provider, payload=payload)
    if not intent:
        return
    _record_webhook_visibility(
        intent,
        external_event_id=external_event_id,
        idempotency_key=idempotency_key,
        target_status=_string_or_none(payload.get("status")),
        event_status="duplicate",
        event_error="duplicate",
        payload=payload,
    )
    db.flush()


def _record_webhook_visibility(
    intent: PaymentIntent,
    *,
    external_event_id: str | None,
    idempotency_key: str | None,
    target_status: str | None,
    event_status: str,
    event_error: str | None,
    payload: dict[str, Any],
) -> None:
    intent.last_webhook_at = datetime.now(timezone.utc)
    intent.last_webhook_event_id = _truncate(external_event_id or idempotency_key, 255)
    intent.last_webhook_status = _truncate(target_status or event_status, 40)
    intent.last_webhook_error = _truncate(PAYMENT_WEBHOOK_ERROR_MESSAGES.get(event_error), 255) if event_error else None
    if target_status == "failed":
        intent.failed_reason = _sanitize_failure_reason(payload)


def _sanitize_failure_reason(payload: dict[str, Any]) -> str | None:
    reason = _string_or_none(payload.get("failed_reason") or payload.get("reason") or payload.get("error_code"))
    return _truncate(reason, 255)


def _truncate(value: str | None, max_length: int) -> str | None:
    if value is None:
        return None
    return value[:max_length]
