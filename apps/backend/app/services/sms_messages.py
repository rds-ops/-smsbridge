from __future__ import annotations

import hashlib
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Order, SmsMessage, SupplierActivation


def record_supplier_sms(
    db: Session,
    *,
    order: Order | None,
    activation: SupplierActivation | None,
    supplier_id: int,
    supplier_sms_id: str,
    phone_number: str,
    phone_from: str | None,
    text: str,
    parsed_code: str | None,
    raw_payload: dict | None = None,
) -> SmsMessage | None:
    if not order:
        return None
    existing = db.scalar(
        select(SmsMessage).where(
            SmsMessage.source == "supplier",
            SmsMessage.supplier_id == supplier_id,
            SmsMessage.external_message_id == supplier_sms_id,
        )
    )
    if existing:
        return existing
    message = SmsMessage(
        order_id=order.id,
        supplier_id=supplier_id,
        supplier_activation_id=activation.id if activation else None,
        source="supplier",
        external_message_id=supplier_sms_id,
        phone_number=phone_number,
        phone_from=phone_from,
        text=text,
        parsed_code=parsed_code,
        raw_payload=raw_payload,
    )
    db.add(message)
    return message


def record_provider_sms(
    db: Session,
    *,
    order: Order,
    provider_order_id: str | None = None,
    phone_from: str | None = None,
    text: str,
    parsed_code: str | None,
    raw_payload: dict | None = None,
) -> SmsMessage:
    # External providers don't always give a stable message id, but we still want
    # idempotent persistence across repeated polling.
    stable_provider_order_id = provider_order_id or order.provider_order_id or ""
    stable_text = text or ""
    stable_code = parsed_code or ""
    external_message_id = hashlib.sha256(
        f"{stable_provider_order_id}\n{stable_text}\n{stable_code}".encode("utf-8")
    ).hexdigest()[:32]

    existing = db.scalar(
        select(SmsMessage).where(
            SmsMessage.order_id == order.id,
            SmsMessage.provider_id == order.provider_id,
            SmsMessage.source == "external_provider",
            SmsMessage.external_message_id == external_message_id,
        )
    )
    if existing:
        return existing
    message = SmsMessage(
        order_id=order.id,
        provider_id=order.provider_id,
        source="external_provider",
        external_message_id=external_message_id,
        phone_number=order.phone_number,
        phone_from=phone_from,
        text=text,
        parsed_code=parsed_code,
        raw_payload=raw_payload,
    )
    db.add(message)
    return message
