from __future__ import annotations
import re
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import api_error
from app.models import (
    Country,
    Order,
    Price,
    Provider,
    Service,
    Supplier,
    SupplierActivation,
    SupplierInventory,
    SupplierSms,
    SupplierTransaction,
)
from app.providers.mock import COUNTRY_PREFIX
from app.services.order_state import OrderStatus, can_transition, is_terminal, transition_order

SUPPLIER_POOL_PROVIDER_CODE = "supplier_pool"
ACTIVE_ACTIVATION_STATUSES = {"reserved", "waiting_sms", "sms_received"}


def normalize_operator(operator: str | None) -> str | None:
    if not operator:
        return None
    value = operator.strip()
    if not value or value.lower() == "any":
        return None
    return value


def supplier_pool_provider(db: Session) -> Provider:
    provider = db.scalar(select(Provider).where(Provider.code == SUPPLIER_POOL_PROVIDER_CODE))
    if provider:
        return provider
    provider = Provider(
        name="Supplier Pool",
        code=SUPPLIER_POOL_PROVIDER_CODE,
        type="supplier_pool",
        status="active",
        priority=150,
        default_markup_percent=Decimal("0.00"),
    )
    db.add(provider)
    db.flush()
    return provider


def validate_service_country(db: Session, service_code: str, country_iso2: str) -> tuple[str, str]:
    service = db.scalar(select(Service).where(Service.code == service_code, Service.is_active.is_(True)))
    if not service:
        raise api_error(400, "INVALID_SERVICE", "Invalid or inactive service")
    country = db.scalar(select(Country).where(Country.iso2 == country_iso2.upper(), Country.is_active.is_(True)))
    if not country:
        raise api_error(400, "INVALID_COUNTRY", "Invalid or inactive country")
    return service.code, country.iso2


def _reference_price(db: Session, service_code: str, country_iso2: str, operator: str | None) -> Decimal:
    stmt = (
        select(Price.final_price)
        .join(Provider, Price.provider_id == Provider.id)
        .where(
            Provider.status == "active",
            Provider.type != "supplier_pool",
            Price.service_code == service_code,
            Price.country_iso2 == country_iso2,
            Price.available_count > 0,
        )
        .order_by(Price.final_price.asc())
    )
    if operator:
        stmt = stmt.where((Price.operator == operator) | (Price.operator.is_(None)))
    price = db.scalar(stmt)
    return Decimal(str(price or "0.5000")).quantize(Decimal("0.0001"))


def sync_supplier_pool_price(db: Session, service_code: str, country_iso2: str, operator: str | None) -> Price:
    provider = supplier_pool_provider(db)
    operator = normalize_operator(operator)
    total_available = db.scalar(
        select(func.coalesce(func.sum(SupplierInventory.available_count), 0))
        .join(Supplier, Supplier.id == SupplierInventory.supplier_id)
        .where(
            Supplier.status == "active",
            SupplierInventory.status == "active",
            SupplierInventory.service_code == service_code,
            SupplierInventory.country_iso2 == country_iso2,
            SupplierInventory.operator.is_(operator) if operator is None else SupplierInventory.operator == operator,
        )
    )
    avg_success = db.scalar(
        select(func.avg(SupplierInventory.success_rate))
        .join(Supplier, Supplier.id == SupplierInventory.supplier_id)
        .where(
            Supplier.status == "active",
            SupplierInventory.status == "active",
            SupplierInventory.service_code == service_code,
            SupplierInventory.country_iso2 == country_iso2,
            SupplierInventory.operator.is_(operator) if operator is None else SupplierInventory.operator == operator,
            SupplierInventory.success_rate.is_not(None),
        )
    )
    final_price = _reference_price(db, service_code, country_iso2, operator)
    provider_cost = (final_price * Decimal("0.70")).quantize(Decimal("0.0001"))
    price = db.scalar(
        select(Price).where(
            Price.provider_id == provider.id,
            Price.service_code == service_code,
            Price.country_iso2 == country_iso2,
            Price.operator.is_(operator) if operator is None else Price.operator == operator,
        )
    )
    if not price:
        price = Price(
            provider_id=provider.id,
            service_code=service_code,
            country_iso2=country_iso2,
            operator=operator,
            provider_cost=provider_cost,
            final_price=final_price,
            available_count=int(total_available or 0),
            delivery_rate=Decimal(str(avg_success or "90.00")),
        )
        db.add(price)
    else:
        price.provider_cost = provider_cost
        price.final_price = final_price
        price.available_count = int(total_available or 0)
        price.delivery_rate = Decimal(str(avg_success or "90.00")).quantize(Decimal("0.01"))
        price.updated_at = datetime.now(timezone.utc)
    db.flush()
    return price


def upsert_inventory(db: Session, supplier: Supplier, items: list) -> int:
    if supplier.status != "active":
        raise HTTPException(status_code=403, detail="Supplier is not active")
    updated = 0
    touched: set[tuple[str, str, str | None]] = set()
    now = datetime.now(timezone.utc)
    for item in items:
        service_code, country_iso2 = validate_service_country(db, item.service_code, item.country_iso2)
        operator = normalize_operator(item.operator)
        inventory = db.scalar(
            select(SupplierInventory).where(
                SupplierInventory.supplier_id == supplier.id,
                SupplierInventory.service_code == service_code,
                SupplierInventory.country_iso2 == country_iso2,
                SupplierInventory.operator.is_(operator) if operator is None else SupplierInventory.operator == operator,
            )
        )
        if not inventory:
            inventory = SupplierInventory(
                supplier_id=supplier.id,
                service_code=service_code,
                country_iso2=country_iso2,
                operator=operator,
            )
            db.add(inventory)
        inventory.available_count = item.available_count
        inventory.success_rate = item.success_rate
        inventory.avg_sms_time_seconds = item.avg_sms_time_seconds
        inventory.status = item.status
        inventory.last_sync_at = now
        updated += 1
        touched.add((service_code, country_iso2, operator))
    db.flush()
    for service_code, country_iso2, operator in touched:
        sync_supplier_pool_price(db, service_code, country_iso2, operator)
    return updated


def select_inventory(
    db: Session,
    service_code: str,
    country_iso2: str,
    operator: str | None,
) -> SupplierInventory | None:
    operator = normalize_operator(operator)
    stmt = (
        select(SupplierInventory)
        .join(Supplier, Supplier.id == SupplierInventory.supplier_id)
        .where(
            Supplier.status == "active",
            SupplierInventory.status == "active",
            SupplierInventory.service_code == service_code,
            SupplierInventory.country_iso2 == country_iso2.upper(),
            SupplierInventory.available_count > 0,
        )
        .with_for_update()
    )
    if operator:
        stmt = stmt.where((SupplierInventory.operator == operator) | (SupplierInventory.operator.is_(None)))
    rows = list(db.scalars(stmt))
    if not rows:
        return None
    rows.sort(
        key=lambda row: (
            Decimal(str(row.success_rate or "0")),
            -Decimal(str(row.supplier.reward_percent)),
            row.available_count,
        ),
        reverse=True,
    )
    return rows[0]


def _fake_supplier_phone(country_iso2: str) -> str:
    prefix = COUNTRY_PREFIX.get(country_iso2.upper(), "1")
    suffix = str(abs(hash(uuid4().hex)) % 900000000 + 100000000)
    return f"+{prefix}{suffix}"


def reserve_supplier_activation(db: Session, order: Order, price: Price, operator: str | None) -> SupplierActivation | None:
    inventory = select_inventory(db, order.service_code, order.country_iso2, operator)
    if not inventory:
        return None
    supplier = inventory.supplier
    inventory.available_count -= 1
    supplier_activation_id = f"sup_act_{uuid4().hex}"
    supplier_reward = (order.price * supplier.reward_percent / Decimal("100")).quantize(Decimal("0.0001"))
    activation = SupplierActivation(
        supplier_id=supplier.id,
        order_id=order.id,
        supplier_activation_id=supplier_activation_id,
        phone_number=_fake_supplier_phone(order.country_iso2),
        service_code=order.service_code,
        country_iso2=order.country_iso2,
        operator=normalize_operator(operator),
        status="waiting_sms",
        client_price=order.price,
        supplier_reward=supplier_reward,
    )
    db.add(activation)
    order.provider_order_id = supplier_activation_id
    order.phone_number = activation.phone_number
    order.provider_cost = supplier_reward
    sync_supplier_pool_price(db, order.service_code, order.country_iso2, activation.operator)
    db.flush()
    return activation


def activation_for_order(db: Session, order_id: int) -> SupplierActivation | None:
    return db.scalar(select(SupplierActivation).where(SupplierActivation.order_id == order_id))


def mark_activation_status(db: Session, order: Order, status: str) -> None:
    activation = activation_for_order(db, order.id)
    if activation and activation.status != "completed":
        activation.status = status


def extract_sms_code(text: str) -> str | None:
    match = re.search(r"(?<!\d)(\d{4,8})(?!\d)", text)
    return match.group(1) if match else None


def push_sms(db: Session, supplier: Supplier, payload) -> tuple[SupplierSms, bool]:
    if supplier.status != "active":
        raise HTTPException(status_code=403, detail="Supplier is not active")
    existing = db.scalar(
        select(SupplierSms).where(
            SupplierSms.supplier_id == supplier.id,
            SupplierSms.supplier_sms_id == payload.supplier_sms_id,
        )
    )
    if existing:
        return existing, True

    activation: SupplierActivation | None = None
    if payload.supplier_activation_id:
        activation = db.scalar(
            select(SupplierActivation).where(
                SupplierActivation.supplier_id == supplier.id,
                SupplierActivation.supplier_activation_id == payload.supplier_activation_id,
            )
        )
    if not activation:
        activation = db.scalar(
            select(SupplierActivation)
            .where(
                SupplierActivation.supplier_id == supplier.id,
                SupplierActivation.phone_number == payload.phone_number,
                SupplierActivation.status.in_(ACTIVE_ACTIVATION_STATUSES),
            )
            .order_by(SupplierActivation.created_at.desc())
        )

    order = db.get(Order, activation.order_id) if activation and activation.order_id else None
    sms_code = extract_sms_code(payload.text)
    sms = SupplierSms(
        supplier_id=supplier.id,
        activation_id=activation.id if activation else None,
        order_id=order.id if order else None,
        supplier_sms_id=payload.supplier_sms_id,
        phone_number=payload.phone_number,
        phone_from=payload.phone_from,
        text=payload.text,
        status="received",
    )
    db.add(sms)
    if activation:
        activation.status = "sms_received"
        activation.sms_text = payload.text
        activation.sms_code = sms_code
    if order and not is_terminal(order.status) and can_transition(order.status, OrderStatus.SMS_RECEIVED):
        transition_order(order, OrderStatus.SMS_RECEIVED, reason="supplier_sms_received")
        order.sms_text = payload.text
        order.sms_code = sms_code
    db.flush()
    return sms, False


def complete_supplier_reward(db: Session, order: Order) -> SupplierTransaction | None:
    activation = activation_for_order(db, order.id)
    if not activation:
        return None
    existing = db.scalar(
        select(SupplierTransaction).where(
            SupplierTransaction.supplier_id == activation.supplier_id,
            SupplierTransaction.order_id == order.id,
            SupplierTransaction.type == "reward",
            SupplierTransaction.status == "completed",
        )
    )
    if existing:
        activation.status = "completed"
        return existing
    supplier = db.scalar(select(Supplier).where(Supplier.id == activation.supplier_id).with_for_update())
    if not supplier:
        return None
    supplier.balance += activation.supplier_reward
    activation.status = "completed"
    tx = SupplierTransaction(
        supplier_id=supplier.id,
        activation_id=activation.id,
        order_id=order.id,
        type="reward",
        amount=activation.supplier_reward,
        status="completed",
        reference=f"order:{order.public_id}",
        tx_metadata={"client_price": str(activation.client_price), "reward_percent": str(supplier.reward_percent)},
    )
    db.add(tx)
    db.flush()
    return tx


def supplier_adjustment(
    db: Session,
    supplier_id: int,
    amount: Decimal,
    reference: str | None = None,
    metadata: dict | None = None,
) -> Supplier:
    supplier = db.scalar(select(Supplier).where(Supplier.id == supplier_id).with_for_update())
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    if supplier.balance + amount < 0:
        raise HTTPException(status_code=400, detail="Supplier balance cannot become negative")
    supplier.balance += amount
    db.add(
        SupplierTransaction(
            supplier_id=supplier.id,
            type="adjustment",
            amount=amount,
            status="completed",
            reference=reference,
            tx_metadata=metadata or {},
        )
    )
    return supplier
