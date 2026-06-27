from __future__ import annotations
import hashlib
import json
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import api_error
from app.models import IdempotencyKey, Order, Price, User
from app.providers.router import candidate_prices, get_adapter
from app.services import limits, sms_messages, suppliers, wallet
from app.services.order_state import OrderStatus, transition_order

ORDER_CREATE_ACTION = "order.create"


def order_create_request_hash(service_code: str, country_iso2: str, operator: str | None = None) -> str:
    payload = {
        "country_iso2": country_iso2.upper(),
        "operator": operator or None,
        "service_code": service_code,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def create_order(db: Session, user: User, service_code: str, country_iso2: str, operator: str | None = None) -> Order:
    service_code, country_iso2 = suppliers.validate_service_country(db, service_code, country_iso2)
    candidates = candidate_prices(db, service_code, country_iso2, operator)
    if not candidates:
        raise api_error(404, "NO_NUMBERS", "No active provider price is available")

    last_error: Exception | None = None
    for price in candidates:
        limits.enforce_can_order(db, user, price.final_price)
        provider = price.provider
        if provider.type == "supplier_pool":
            order = Order(
                user_id=user.id,
                provider_id=provider.id,
                service_code=service_code,
                country_iso2=country_iso2.upper(),
                operator=operator,
                status=OrderStatus.CREATED,
                price=price.final_price,
                provider_cost=price.provider_cost,
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=settings.mock_order_timeout_seconds),
            )
            db.add(order)
            db.flush()
            wallet.hold(db, user.id, order.id, order.price)
            try:
                activation = suppliers.reserve_supplier_activation(db, order, price, operator)
            except Exception as exc:
                wallet.refund(db, user.id, order.id, order.price)
                transition_order(order, OrderStatus.FAILED, db=db, actor_type="system", reason="supplier_reservation_failed")
                last_error = exc
                continue
            if not activation:
                wallet.refund(db, user.id, order.id, order.price)
                transition_order(order, OrderStatus.FAILED, db=db, actor_type="system", reason="supplier_reservation_unavailable")
                last_error = RuntimeError("No active supplier inventory")
                continue
            transition_order(order, OrderStatus.WAITING_SMS, db=db, actor_type="system", reason="supplier_pool_reserved")
            return order
        order = Order(
            user_id=user.id,
            provider_id=provider.id,
            service_code=service_code,
            country_iso2=country_iso2.upper(),
            operator=operator,
            status=OrderStatus.CREATED,
            price=price.final_price,
            provider_cost=price.provider_cost,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=settings.mock_order_timeout_seconds),
        )
        db.add(order)
        db.flush()
        wallet.hold(db, user.id, order.id, order.price)
        adapter = get_adapter(provider)
        try:
            reservation = adapter.get_number(service_code, country_iso2.upper(), operator)
        except Exception as exc:
            wallet.refund(db, user.id, order.id, order.price)
            transition_order(order, OrderStatus.FAILED, db=db, actor_type="system", reason="provider_reservation_failed")
            last_error = exc
            continue

        order.provider_order_id = reservation.provider_order_id
        order.phone_number = reservation.phone_number
        transition_order(order, OrderStatus.WAITING_SMS, db=db, actor_type="system", reason="provider_reserved")
        return order

    raise api_error(502, "PROVIDER_UNAVAILABLE", f"All providers failed: {last_error}")


def create_order_idempotent(
    db: Session,
    user: User,
    service_code: str,
    country_iso2: str,
    operator: str | None,
    idempotency_key: str | None,
) -> Order:
    if not idempotency_key:
        return create_order(db, user, service_code, country_iso2, operator)

    key = idempotency_key.strip()
    if not key:
        return create_order(db, user, service_code, country_iso2, operator)
    if len(key) > 255:
        raise HTTPException(status_code=400, detail="Idempotency-Key is too long")

    request_hash = order_create_request_hash(service_code, country_iso2, operator)
    record = IdempotencyKey(
        user_id=user.id,
        key=key,
        action=ORDER_CREATE_ACTION,
        request_hash=request_hash,
        status="in_progress",
    )
    db.add(record)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(IdempotencyKey).where(
                IdempotencyKey.user_id == user.id,
                IdempotencyKey.action == ORDER_CREATE_ACTION,
                IdempotencyKey.key == key,
            )
        )
        if not existing:
            raise
        if existing.request_hash != request_hash:
            raise HTTPException(status_code=409, detail="Idempotency-Key was already used with a different request")
        if not existing.order_id or existing.status != "completed":
            raise HTTPException(status_code=409, detail="Idempotent request is still processing")
        order = db.get(Order, existing.order_id)
        if not order:
            raise HTTPException(status_code=409, detail="Idempotency record has no order result")
        return order

    order = create_order(db, user, service_code, country_iso2, operator)
    record.order_id = order.id
    record.status = "completed"
    db.flush()
    return order


def create_order_idempotent_transactional(
    db: Session,
    user: User,
    service_code: str,
    country_iso2: str,
    operator: str | None,
    idempotency_key: str | None,
) -> Order:
    try:
        order = create_order_idempotent(db, user, service_code, country_iso2, operator, idempotency_key)
        db.commit()
        db.refresh(order)
        suppliers.pop_pending_reservation_failures(db)
        return order
    except Exception:
        reservation_failures = suppliers.pop_pending_reservation_failures(db)
        db.rollback()
        suppliers.persist_reservation_failures(db, reservation_failures)
        raise


def get_user_order(db: Session, user: User, public_id: str) -> Order:
    order = db.scalar(select(Order).where(Order.public_id == public_id, Order.user_id == user.id))
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


def cancel_order(db: Session, order: Order, actor_user_id: int | None = None) -> Order:
    if order.status in {OrderStatus.CANCELLED, OrderStatus.EXPIRED, OrderStatus.REFUNDED}:
        return order
    if order.status in {OrderStatus.COMPLETED, OrderStatus.FAILED}:
        raise HTTPException(status_code=409, detail="Order can no longer be cancelled")
    provider = order.provider
    if order.provider_order_id and provider.type != "supplier_pool":
        get_adapter(provider).cancel_order(order.provider_order_id)
    wallet.refund(db, order.user_id, order.id, order.price)
    transition_order(
        order,
        OrderStatus.CANCELLED,
        db=db,
        actor_type="buyer",
        actor_user_id=actor_user_id,
        reason="buyer_cancelled",
    )
    suppliers.mark_activation_status(db, order, OrderStatus.CANCELLED)
    return order


def finish_order(db: Session, order: Order, actor_user_id: int | None = None) -> Order:
    if order.status == OrderStatus.COMPLETED:
        return order
    if order.status != OrderStatus.SMS_RECEIVED:
        raise HTTPException(status_code=409, detail="Order can only be finished after SMS is received")
    if order.provider_order_id and order.provider.type != "supplier_pool":
        get_adapter(order.provider).finish_order(order.provider_order_id)
    wallet.capture(db, order.user_id, order.id, order.price)
    transition_order(
        order,
        OrderStatus.COMPLETED,
        db=db,
        actor_type="buyer",
        actor_user_id=actor_user_id,
        reason="buyer_finished",
    )
    suppliers.complete_supplier_reward(db, order)
    return order


def refund_order(db: Session, order: Order, actor_user_id: int | None = None) -> Order:
    if order.status in {OrderStatus.REFUNDED, OrderStatus.EXPIRED, OrderStatus.CANCELLED}:
        return order
    wallet.refund(db, order.user_id, order.id, order.price)
    transition_order(
        order,
        OrderStatus.REFUNDED,
        db=db,
        actor_type="admin",
        actor_user_id=actor_user_id,
        reason="admin_refund",
    )
    suppliers.mark_activation_status(db, order, OrderStatus.REFUNDED)
    return order


def poll_order(db: Session, order: Order) -> Order:
    now = datetime.now(timezone.utc)
    if order.status != OrderStatus.WAITING_SMS:
        return order
    expires_at = order.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        wallet.refund(db, order.user_id, order.id, order.price)
        transition_order(order, OrderStatus.EXPIRED, db=db, actor_type="worker", reason="timeout")
        suppliers.mark_activation_status(db, order, OrderStatus.EXPIRED)
        return order

    if order.provider.type == "supplier_pool":
        return order

    status = get_adapter(order.provider).get_order_status(order.provider_order_id or "")
    if status.status == OrderStatus.SMS_RECEIVED:
        transition_order(order, OrderStatus.SMS_RECEIVED, db=db, actor_type="system", reason="provider_sms_received")
        order.sms_code = status.sms_code
        order.sms_text = status.sms_text
        sms_messages.record_provider_sms(
            db,
            order=order,
            provider_order_id=order.provider_order_id,
            text=status.sms_text or "",
            parsed_code=status.sms_code,
            raw_payload={"provider_order_id": order.provider_order_id, "status": status.status},
        )
    elif status.status in {"timeout", "failed"}:
        wallet.refund(db, order.user_id, order.id, order.price)
        target_status = OrderStatus.EXPIRED if status.status == "timeout" else OrderStatus.FAILED
        transition_order(order, target_status, db=db, actor_type="system", reason=f"provider_{status.status}")
        suppliers.mark_activation_status(db, order, order.status)
    return order


def sync_mock_prices(db: Session) -> None:
    providers = list(db.scalars(select(Price.provider_id).distinct()))
    _ = providers
