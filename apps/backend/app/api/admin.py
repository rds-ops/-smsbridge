from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.core.security import generate_api_key, hash_api_key
from app.db.session import get_db
from app.models import (
    ApiRequestLog,
    AuditLog,
    Order,
    OrderEvent,
    Provider,
    Supplier,
    SupplierActivation,
    SupplierInventory,
    SupplierSms,
    SupplierTransaction,
    User,
    WalletTransaction,
)
from app.schemas.admin import (
    AdjustmentIn,
    DepositIn,
    AdminOrderOut,
    OrderEventOut,
    ProviderIn,
    ProviderOut,
    UserDetail,
    UserLimitsPatch,
    UserStatusPatch,
)
from app.schemas.common import ApiRequestLogOut, AuditLogOut, OrderOut, WalletOut
from app.schemas.supplier import (
    AdminSupplierInventoryOut,
    SupplierAdjustmentIn,
    SupplierActivationOut,
    SupplierApiKeyOut,
    SupplierCreate,
    SupplierListOut,
    SupplierOut,
    SupplierPatch,
    SupplierSmsOut,
    SupplierTransactionOut,
)
from app.services.audit import add_audit_log
from app.services.limits import apply_tier_limits
from app.services.orders import refund_order
from app.services.suppliers import supplier_adjustment
from app.services.wallet import adjustment, deposit

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserDetail])
def users(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return list(db.scalars(select(User).order_by(User.created_at.desc()).limit(200)))


@router.get("/users/{user_id}", response_model=UserDetail)
def user_detail(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/users/{user_id}/status", response_model=UserDetail)
def update_status(user_id: int, payload: UserStatusPatch, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.status = payload.status
    add_audit_log(db, "user.status.update", "user", str(user.id), admin.id, {"status": payload.status})
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}/limits", response_model=UserDetail)
def update_limits(user_id: int, payload: UserLimitsPatch, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if not user or not user.limit:
        raise HTTPException(status_code=404, detail="User or limits not found")
    data = payload.model_dump(exclude_unset=True)
    tier = data.pop("tier", None)
    if tier:
        user.tier = tier
        apply_tier_limits(user, tier)
    for key, value in data.items():
        setattr(user.limit, key, value)
    add_audit_log(db, "user.limits.update", "user", str(user.id), admin.id, payload.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(user)
    return user


@router.get("/orders", response_model=list[AdminOrderOut])
def orders(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return list(db.scalars(select(Order).order_by(Order.created_at.desc()).limit(200)))


@router.get("/orders/{order_id}", response_model=AdminOrderOut)
def order_detail(order_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.get("/orders/{order_id}/events", response_model=list[OrderEventOut])
def order_events(order_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return list(
        db.scalars(
            select(OrderEvent)
            .where(OrderEvent.order_id == order_id)
            .order_by(OrderEvent.created_at.asc(), OrderEvent.id.asc())
        )
    )


@router.get("/providers", response_model=list[ProviderOut])
def providers(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return list(db.scalars(select(Provider).order_by(Provider.priority.desc())))


@router.get("/suppliers", response_model=list[SupplierListOut])
def suppliers(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    rows = db.execute(
        select(Supplier, func.count(SupplierInventory.id))
        .outerjoin(SupplierInventory, SupplierInventory.supplier_id == Supplier.id)
        .group_by(Supplier.id)
        .order_by(Supplier.created_at.desc())
        .limit(200)
    ).all()
    return [SupplierListOut.model_validate(supplier).model_copy(update={"inventory_count": count}) for supplier, count in rows]


@router.post("/suppliers", response_model=SupplierOut)
def create_supplier(payload: SupplierCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    supplier = Supplier(**payload.model_dump())
    db.add(supplier)
    db.flush()
    add_audit_log(db, "supplier.create", "supplier", str(supplier.id), admin.id, payload.model_dump())
    db.commit()
    db.refresh(supplier)
    return supplier


@router.get("/suppliers/{supplier_id}", response_model=SupplierOut)
def supplier_detail(supplier_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


@router.patch("/suppliers/{supplier_id}", response_model=SupplierOut)
def update_supplier(supplier_id: int, payload: SupplierPatch, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(supplier, key, value)
    add_audit_log(db, "supplier.update", "supplier", str(supplier.id), admin.id, data)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.post("/suppliers/{supplier_id}/api-key/regenerate", response_model=SupplierApiKeyOut)
def regenerate_supplier_api_key(supplier_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    raw = generate_api_key().replace("sb_live_", "sbsup_live_", 1)
    supplier.api_key_hash = hash_api_key(raw)
    add_audit_log(db, "supplier.api_key.regenerate", "supplier", str(supplier.id), admin.id, {})
    db.commit()
    return SupplierApiKeyOut(api_key=raw)


@router.get("/suppliers/{supplier_id}/inventory", response_model=list[AdminSupplierInventoryOut])
def supplier_inventory(supplier_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return list(
        db.scalars(
            select(SupplierInventory)
            .where(SupplierInventory.supplier_id == supplier_id)
            .order_by(SupplierInventory.updated_at.desc())
            .limit(500)
        )
    )


@router.get("/suppliers/{supplier_id}/activations", response_model=list[SupplierActivationOut])
def supplier_activations(supplier_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return list(
        db.scalars(
            select(SupplierActivation)
            .where(SupplierActivation.supplier_id == supplier_id)
            .order_by(SupplierActivation.created_at.desc())
            .limit(500)
        )
    )


@router.get("/suppliers/{supplier_id}/sms", response_model=list[SupplierSmsOut])
def supplier_sms(supplier_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return list(
        db.scalars(
            select(SupplierSms)
            .where(SupplierSms.supplier_id == supplier_id)
            .order_by(SupplierSms.created_at.desc())
            .limit(500)
        )
    )


@router.get("/suppliers/{supplier_id}/transactions", response_model=list[SupplierTransactionOut])
def supplier_transactions(supplier_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return list(
        db.scalars(
            select(SupplierTransaction)
            .where(SupplierTransaction.supplier_id == supplier_id)
            .order_by(SupplierTransaction.created_at.desc())
            .limit(500)
        )
    )


@router.post("/suppliers/{supplier_id}/adjustment", response_model=SupplierOut)
def supplier_manual_adjustment(
    supplier_id: int,
    payload: SupplierAdjustmentIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    supplier = supplier_adjustment(db, supplier_id, payload.amount, payload.reference, payload.metadata)
    add_audit_log(db, "supplier.adjustment", "supplier", str(supplier.id), admin.id, payload.model_dump())
    db.commit()
    db.refresh(supplier)
    return supplier


@router.post("/providers", response_model=ProviderOut)
def create_provider(payload: ProviderIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    provider = Provider(**payload.model_dump())
    db.add(provider)
    add_audit_log(db, "provider.create", "provider", provider.code, admin.id, payload.model_dump())
    db.commit()
    db.refresh(provider)
    return provider


@router.patch("/providers/{provider_id}", response_model=ProviderOut)
def update_provider(provider_id: int, payload: ProviderIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    provider = db.get(Provider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    for key, value in payload.model_dump().items():
        setattr(provider, key, value)
    add_audit_log(db, "provider.update", "provider", str(provider.id), admin.id, payload.model_dump())
    db.commit()
    db.refresh(provider)
    return provider


@router.post("/wallets/deposit", response_model=WalletOut)
def manual_deposit(payload: DepositIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    wallet = deposit(db, payload.user_id, payload.amount, payload.reference)
    add_audit_log(db, "wallet.deposit", "user", str(payload.user_id), admin.id, payload.model_dump())
    db.commit()
    db.refresh(wallet)
    return wallet


@router.post("/wallets/adjustment", response_model=WalletOut)
def manual_adjustment(payload: AdjustmentIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    wallet = adjustment(db, payload.user_id, payload.amount, payload.reference, payload.metadata)
    add_audit_log(db, "wallet.adjustment", "user", str(payload.user_id), admin.id, payload.model_dump())
    db.commit()
    db.refresh(wallet)
    return wallet


@router.post("/orders/{order_id}/refund", response_model=OrderOut)
def admin_refund(order_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order = refund_order(db, order, actor_user_id=admin.id)
    add_audit_log(db, "order.refund", "order", str(order.id), admin.id, {})
    db.commit()
    db.refresh(order)
    return order


@router.get("/audit-logs", response_model=list[AuditLogOut])
def audit_logs(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return list(db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(200)))


@router.get("/api-request-logs", response_model=list[ApiRequestLogOut])
def api_request_logs(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return list(db.scalars(select(ApiRequestLog).order_by(ApiRequestLog.created_at.desc()).limit(200)))


@router.get("/metrics")
def metrics(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    total_users = db.scalar(select(func.count(User.id)))
    orders_today = db.scalar(select(func.count(Order.id)).where(Order.created_at >= start))
    successful = db.scalar(select(func.count(Order.id)).where(Order.created_at >= start, Order.status == "completed"))
    failed = db.scalar(select(func.count(Order.id)).where(Order.created_at >= start, Order.status.in_(["failed", "expired"])))
    captured = db.scalar(
        select(func.coalesce(func.sum(WalletTransaction.amount), Decimal("0"))).where(
            WalletTransaction.created_at >= start, WalletTransaction.type == "capture"
        )
    )
    refunds = db.scalar(
        select(func.coalesce(func.sum(WalletTransaction.amount), Decimal("0"))).where(
            WalletTransaction.created_at >= start, WalletTransaction.type == "refund"
        )
    )
    provider_cost = db.scalar(
        select(func.coalesce(func.sum(Order.provider_cost), Decimal("0"))).where(
            Order.created_at >= start, Order.status == "completed"
        )
    )
    supplier_rewards = db.scalar(
        select(func.coalesce(func.sum(SupplierTransaction.amount), Decimal("0"))).where(
            SupplierTransaction.created_at >= start,
            SupplierTransaction.type == "reward",
            SupplierTransaction.status == "completed",
        )
    )
    top_services = db.execute(
        select(Order.service_code, func.count(Order.id)).where(Order.created_at >= start).group_by(Order.service_code).limit(5)
    ).all()
    top_countries = db.execute(
        select(Order.country_iso2, func.count(Order.id)).where(Order.created_at >= start).group_by(Order.country_iso2).limit(5)
    ).all()
    return {
        "total_users": total_users,
        "orders_today": orders_today,
        "successful_orders_today": successful,
        "failed_expired_orders_today": failed,
        "gross_revenue_today": captured,
        "provider_cost_today": provider_cost,
        "supplier_reward_today": supplier_rewards,
        "gross_profit_today": Decimal(str(captured)) - Decimal(str(provider_cost)),
        "refund_amount_today": refunds,
        "top_services": [{"service_code": row[0], "orders": row[1]} for row in top_services],
        "top_countries": [{"country_iso2": row[0], "orders": row[1]} for row in top_countries],
    }
