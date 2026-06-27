from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_supplier, require_active_supplier
from app.db.session import get_db
from app.models import Order, SmsMessage, Supplier, SupplierActivation, SupplierInventory, SupplierPayoutRequest, SupplierTransaction
from app.schemas.supplier import (
    SupplierActivationSafeOut,
    SupplierInventoryOut,
    SupplierInventoryUpdateIn,
    SupplierInventoryUpdateOut,
    SupplierMeOut,
    SupplierPayoutRequestCreateIn,
    SupplierPayoutRequestOut,
    SupplierSmsIn,
    SupplierSmsPushOut,
    SupplierTransactionSafeOut,
)
from app.services.suppliers import create_supplier_payout_request, push_sms, upsert_inventory

router = APIRouter(prefix="/supplier/v1", tags=["supplier-api"])


@router.get("/me", response_model=SupplierMeOut)
def me(supplier: Supplier = Depends(get_current_supplier)):
    return supplier


@router.get("/inventory", response_model=list[SupplierInventoryOut])
def inventory(db: Session = Depends(get_db), supplier: Supplier = Depends(get_current_supplier)):
    return list(
        db.scalars(
            select(SupplierInventory)
            .where(SupplierInventory.supplier_id == supplier.id)
            .order_by(SupplierInventory.updated_at.desc())
        )
    )


@router.post("/inventory/update", response_model=SupplierInventoryUpdateOut)
def inventory_update(
    payload: SupplierInventoryUpdateIn,
    db: Session = Depends(get_db),
    supplier: Supplier = Depends(require_active_supplier),
):
    updated = upsert_inventory(db, supplier, payload.items)
    db.commit()
    return SupplierInventoryUpdateOut(updated=updated)


@router.post("/payout-requests", response_model=SupplierPayoutRequestOut)
def create_payout_request(
    payload: SupplierPayoutRequestCreateIn,
    db: Session = Depends(get_db),
    supplier: Supplier = Depends(require_active_supplier),
):
    payout = create_supplier_payout_request(
        db,
        supplier_id=supplier.id,
        amount=payload.amount,
        payout_method=payload.payout_method,
        payout_address=payload.payout_address,
    )
    db.commit()
    db.refresh(payout)
    return payout


@router.get("/payout-requests", response_model=list[SupplierPayoutRequestOut])
def payout_requests(db: Session = Depends(get_db), supplier: Supplier = Depends(get_current_supplier)):
    return list(
        db.scalars(
            select(SupplierPayoutRequest)
            .where(SupplierPayoutRequest.supplier_id == supplier.id)
            .order_by(SupplierPayoutRequest.created_at.desc(), SupplierPayoutRequest.id.desc())
            .limit(200)
        )
    )


@router.get("/activations", response_model=list[SupplierActivationSafeOut])
def activations(
    status: str | None = Query(default=None, max_length=40),
    service: str | None = Query(default=None, max_length=50),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    phone: str | None = Query(default=None, max_length=40),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    supplier: Supplier = Depends(get_current_supplier),
):
    stmt = (
        select(
            SupplierActivation,
            Order.public_id,
            func.count(SmsMessage.id).label("sms_count"),
            func.max(SmsMessage.created_at).label("latest_sms_at"),
        )
        .outerjoin(Order, SupplierActivation.order_id == Order.id)
        .outerjoin(SmsMessage, SmsMessage.supplier_activation_id == SupplierActivation.id)
        .where(SupplierActivation.supplier_id == supplier.id)
        .group_by(SupplierActivation.id, Order.public_id)
    )
    if status:
        stmt = stmt.where(SupplierActivation.status == status)
    if service:
        stmt = stmt.where(SupplierActivation.service_code == service)
    if country:
        stmt = stmt.where(SupplierActivation.country_iso2 == country.upper())
    if phone:
        stmt = stmt.where(SupplierActivation.phone_number == phone)
    rows = db.execute(
        stmt.order_by(SupplierActivation.created_at.desc(), SupplierActivation.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return [
        SupplierActivationSafeOut(
            id=activation.id,
            supplier_activation_id=activation.supplier_activation_id,
            phone_number=activation.phone_number,
            service_code=activation.service_code,
            country_iso2=activation.country_iso2,
            operator=activation.operator,
            status=activation.status,
            order_public_id=order_public_id,
            sms_count=int(sms_count or 0),
            latest_sms_at=latest_sms_at,
            created_at=activation.created_at,
            updated_at=activation.updated_at,
        )
        for activation, order_public_id, sms_count, latest_sms_at in rows
    ]


@router.get("/transactions", response_model=list[SupplierTransactionSafeOut])
def transactions(
    tx_type: str | None = Query(default=None, alias="type", max_length=40),
    status: str | None = Query(default=None, max_length=40),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    supplier: Supplier = Depends(get_current_supplier),
):
    stmt = (
        select(SupplierTransaction, Order.public_id)
        .outerjoin(Order, SupplierTransaction.order_id == Order.id)
        .where(SupplierTransaction.supplier_id == supplier.id)
    )
    if tx_type:
        stmt = stmt.where(SupplierTransaction.type == tx_type)
    if status:
        stmt = stmt.where(SupplierTransaction.status == status)
    rows = db.execute(
        stmt.order_by(SupplierTransaction.created_at.desc(), SupplierTransaction.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return [
        SupplierTransactionSafeOut(
            type=transaction.type,
            amount=transaction.amount,
            currency=supplier.currency,
            status=transaction.status,
            reference=transaction.reference,
            order_public_id=order_public_id,
            created_at=transaction.created_at,
        )
        for transaction, order_public_id in rows
    ]


@router.post("/sms", response_model=SupplierSmsPushOut)
def sms_push(
    payload: SupplierSmsIn,
    db: Session = Depends(get_db),
    supplier: Supplier = Depends(require_active_supplier),
):
    _sms, duplicate = push_sms(db, supplier, payload)
    db.commit()
    return SupplierSmsPushOut(duplicate=duplicate)
