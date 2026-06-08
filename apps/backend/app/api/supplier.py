from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_supplier, require_active_supplier
from app.db.session import get_db
from app.models import Supplier, SupplierInventory, SupplierPayoutRequest
from app.schemas.supplier import (
    SupplierInventoryOut,
    SupplierInventoryUpdateIn,
    SupplierInventoryUpdateOut,
    SupplierMeOut,
    SupplierPayoutRequestCreateIn,
    SupplierPayoutRequestOut,
    SupplierSmsIn,
    SupplierSmsPushOut,
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


@router.post("/sms", response_model=SupplierSmsPushOut)
def sms_push(
    payload: SupplierSmsIn,
    db: Session = Depends(get_db),
    supplier: Supplier = Depends(require_active_supplier),
):
    _sms, duplicate = push_sms(db, supplier, payload)
    db.commit()
    return SupplierSmsPushOut(duplicate=duplicate)
