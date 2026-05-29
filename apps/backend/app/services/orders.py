from __future__ import annotations
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import api_error
from app.models import Order, Price, User
from app.providers.router import candidate_prices, get_adapter
from app.services import limits, suppliers, wallet
from app.services.order_state import OrderStatus, transition_order


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
            transition_order(order, OrderStatus.WAITING_SMS, reason="supplier_pool_reserved")
            db.add(order)
            db.flush()
            activation = suppliers.reserve_supplier_activation(db, order, price, operator)
            if not activation:
                db.delete(order)
                last_error = RuntimeError("No active supplier inventory")
                continue
            wallet.hold(db, user.id, order.id, order.price)
            return order
        adapter = get_adapter(provider)
        try:
            reservation = adapter.get_number(service_code, country_iso2.upper(), operator)
        except Exception as exc:
            last_error = exc
            continue

        order = Order(
            user_id=user.id,
            provider_id=provider.id,
            provider_order_id=reservation.provider_order_id,
            service_code=service_code,
            country_iso2=country_iso2.upper(),
            operator=operator,
            phone_number=reservation.phone_number,
            status=OrderStatus.CREATED,
            price=price.final_price,
            provider_cost=price.provider_cost,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=settings.mock_order_timeout_seconds),
        )
        transition_order(order, OrderStatus.WAITING_SMS, reason="provider_reserved")
        db.add(order)
        db.flush()
        wallet.hold(db, user.id, order.id, order.price)
        return order

    raise api_error(502, "PROVIDER_UNAVAILABLE", f"All providers failed: {last_error}")


def get_user_order(db: Session, user: User, public_id: str) -> Order:
    order = db.scalar(select(Order).where(Order.public_id == public_id, Order.user_id == user.id))
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


def cancel_order(db: Session, order: Order) -> Order:
    if order.status in {OrderStatus.CANCELLED, OrderStatus.EXPIRED, OrderStatus.REFUNDED}:
        return order
    if order.status in {OrderStatus.COMPLETED, OrderStatus.FAILED}:
        raise HTTPException(status_code=409, detail="Order can no longer be cancelled")
    provider = order.provider
    if order.provider_order_id and provider.type != "supplier_pool":
        get_adapter(provider).cancel_order(order.provider_order_id)
    wallet.refund(db, order.user_id, order.id, order.price)
    transition_order(order, OrderStatus.CANCELLED, reason="buyer_cancelled")
    suppliers.mark_activation_status(db, order, OrderStatus.CANCELLED)
    return order


def finish_order(db: Session, order: Order) -> Order:
    if order.status == OrderStatus.COMPLETED:
        return order
    if order.status != OrderStatus.SMS_RECEIVED:
        raise HTTPException(status_code=409, detail="Order can only be finished after SMS is received")
    if order.provider_order_id and order.provider.type != "supplier_pool":
        get_adapter(order.provider).finish_order(order.provider_order_id)
    wallet.capture(db, order.user_id, order.id, order.price)
    transition_order(order, OrderStatus.COMPLETED, reason="buyer_finished")
    suppliers.complete_supplier_reward(db, order)
    return order


def refund_order(db: Session, order: Order) -> Order:
    if order.status in {OrderStatus.REFUNDED, OrderStatus.EXPIRED, OrderStatus.CANCELLED}:
        return order
    wallet.refund(db, order.user_id, order.id, order.price)
    transition_order(order, OrderStatus.REFUNDED, reason="admin_refund")
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
        transition_order(order, OrderStatus.EXPIRED, reason="timeout")
        suppliers.mark_activation_status(db, order, OrderStatus.EXPIRED)
        return order

    if order.provider.type == "supplier_pool":
        return order

    status = get_adapter(order.provider).get_order_status(order.provider_order_id or "")
    if status.status == OrderStatus.SMS_RECEIVED:
        transition_order(order, OrderStatus.SMS_RECEIVED, reason="provider_sms_received")
        order.sms_code = status.sms_code
        order.sms_text = status.sms_text
    elif status.status in {"timeout", "failed"}:
        wallet.refund(db, order.user_id, order.id, order.price)
        target_status = OrderStatus.EXPIRED if status.status == "timeout" else OrderStatus.FAILED
        transition_order(order, target_status, reason=f"provider_{status.status}")
        suppliers.mark_activation_status(db, order, order.status)
    return order


def sync_mock_prices(db: Session) -> None:
    providers = list(db.scalars(select(Price.provider_id).distinct()))
    _ = providers
