from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_supplier, require_active_supplier
from app.db.session import get_db
from app.models import Order, SmsMessage, Supplier, SupplierActivation, SupplierApplication, SupplierInventory, SupplierPayoutRequest, SupplierTransaction
from app.schemas.supplier import (
    SupplierActivationSafeOut,
    SupplierApplicationCreateIn,
    SupplierApplicationReceivedOut,
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
from app.services.audit import add_audit_log
from app.services.suppliers import create_supplier_payout_request, push_sms, upsert_inventory

router = APIRouter(prefix="/supplier/v1", tags=["supplier-api"])


def _clean_text(value: str) -> str:
    return " ".join(value.strip().split())


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _safe_url(value: str | None, field_name: str) -> str | None:
    cleaned = _clean_optional(value)
    if cleaned and not cleaned.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail=f"{field_name} must be an HTTP(S) URL")
    return cleaned


@router.post("/applications", response_model=SupplierApplicationReceivedOut)
def create_supplier_application(payload: SupplierApplicationCreateIn, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        raise HTTPException(status_code=400, detail="Invalid email")
    application = SupplierApplication(
        contact_name=_clean_text(payload.contact_name),
        email=email,
        contact_handle=_clean_text(payload.contact_handle),
        country_market=_clean_text(payload.country_market),
        number_type=payload.number_type,
        estimated_daily_volume=payload.estimated_daily_volume,
        estimated_monthly_volume=payload.estimated_monthly_volume,
        integration_availability=payload.integration_availability,
        inventory_description=payload.inventory_description.strip(),
        api_url=_safe_url(payload.api_url, "api_url"),
        equipment_details=_clean_optional(payload.equipment_details),
        website=_safe_url(payload.website, "website"),
    )
    db.add(application)
    db.flush()
    add_audit_log(
        db,
        "supplier_application.create",
        "supplier_application",
        str(application.id),
        None,
        {"public_id": application.public_id, "status": application.status, "number_type": application.number_type},
    )
    db.commit()
    return SupplierApplicationReceivedOut(public_id=application.public_id)


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
