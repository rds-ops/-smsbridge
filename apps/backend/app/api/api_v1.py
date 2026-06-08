from __future__ import annotations
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_current_user_or_api_key
from app.core.security import generate_api_key, hash_api_key
from app.db.session import get_db
from app.models import Country, Order, Price, Service, User, WalletTransaction
from app.schemas.common import (
    BuyerPriceOut,
    BuyerWalletTransactionOut,
    BuyerApiKeyCreateIn,
    BuyerApiKeyCreateOut,
    BuyerApiKeyOut,
    CountryOut,
    MessageOut,
    OrderCreate,
    OrderOut,
    PaymentIntentCreateIn,
    PaymentIntentOut,
    ServiceOut,
    UserLimitOut,
    WalletOut,
)
from app.services import orders as order_service
from app.services import payment_intents as payment_intent_service
from app.services import buyer_api_keys as buyer_api_key_service

router = APIRouter(prefix="/api/v1", tags=["user-api"])


@router.get("/balance", response_model=WalletOut)
def balance(user: User = Depends(get_current_user_or_api_key)):
    return user.wallet


@router.get("/services", response_model=list[ServiceOut])
def services(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return list(db.scalars(select(Service).where(Service.is_active.is_(True)).order_by(Service.code)))


@router.get("/countries", response_model=list[CountryOut])
def countries(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return list(db.scalars(select(Country).where(Country.is_active.is_(True)).order_by(Country.iso2)))


@router.get("/prices", response_model=list[BuyerPriceOut])
def prices(
    service_code: str | None = Query(default=None),
    country_iso2: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_api_key),
):
    stmt = select(Price).where(Price.available_count > 0)
    if service_code:
        stmt = stmt.where(Price.service_code == service_code)
    if country_iso2:
        stmt = stmt.where(Price.country_iso2 == country_iso2.upper())
    stmt = stmt.order_by(Price.service_code, Price.country_iso2, Price.final_price)
    return list(db.scalars(stmt))


@router.post("/orders", response_model=OrderOut)
def create_order(
    payload: OrderCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_api_key),
):
    return order_service.create_order_idempotent_transactional(
        db,
        user,
        payload.service_code,
        payload.country_iso2,
        payload.operator,
        idempotency_key,
    )


@router.get("/orders", response_model=list[OrderOut])
def list_orders(
    status: str | None = None,
    service: str | None = None,
    country: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(Order).where(Order.user_id == user.id)
    if status:
        stmt = stmt.where(Order.status == status)
    if service:
        stmt = stmt.where(Order.service_code == service)
    if country:
        stmt = stmt.where(Order.country_iso2 == country.upper())
    return list(db.scalars(stmt.order_by(Order.created_at.desc()).limit(100)))


@router.get("/orders/{public_id}", response_model=OrderOut)
def get_order(public_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user_or_api_key)):
    return order_service.get_user_order(db, user, public_id)


@router.post("/orders/{public_id}/cancel", response_model=OrderOut)
def cancel_order(public_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user_or_api_key)):
    order = order_service.get_user_order(db, user, public_id)
    order = order_service.cancel_order(db, order, actor_user_id=user.id)
    db.commit()
    db.refresh(order)
    return order


@router.post("/orders/{public_id}/finish", response_model=OrderOut)
def finish_order(public_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user_or_api_key)):
    order = order_service.get_user_order(db, user, public_id)
    order = order_service.finish_order(db, order, actor_user_id=user.id)
    db.commit()
    db.refresh(order)
    return order


@router.post("/api-key/regenerate")
def regenerate_api_key(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    raw = generate_api_key()
    user.api_key_hash = hash_api_key(raw)
    db.commit()
    return {"api_key": raw, "message": "Store this key now. It will not be shown again."}


@router.post("/api-keys", response_model=BuyerApiKeyCreateOut)
def create_api_key(
    payload: BuyerApiKeyCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    api_key, raw = buyer_api_key_service.create_buyer_api_key(
        db,
        user,
        name=payload.name,
        scopes=payload.scopes,
    )
    db.commit()
    db.refresh(api_key)
    return {
        "id": api_key.id,
        "public_id": api_key.public_id,
        "name": api_key.name,
        "key_prefix": api_key.key_prefix,
        "status": api_key.status,
        "scopes": api_key.scopes,
        "last_used_at": api_key.last_used_at,
        "created_at": api_key.created_at,
        "revoked_at": api_key.revoked_at,
        "api_key": raw,
    }


@router.get("/api-keys", response_model=list[BuyerApiKeyOut])
def list_api_keys(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return buyer_api_key_service.list_buyer_api_keys(db, user)


@router.post("/api-keys/{public_id}/revoke", response_model=BuyerApiKeyOut)
def revoke_api_key(public_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    api_key = buyer_api_key_service.revoke_buyer_api_key(db, user, public_id)
    db.commit()
    db.refresh(api_key)
    return api_key


@router.get("/limits", response_model=UserLimitOut)
def limits(user: User = Depends(get_current_user_or_api_key)):
    if not user.limit:
        raise HTTPException(status_code=404, detail="Limits not configured")
    return user.limit


@router.get("/wallet/transactions", response_model=list[BuyerWalletTransactionOut])
def wallet_transactions(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_api_key),
):
    stmt = (
        select(WalletTransaction, Order.public_id)
        .outerjoin(Order, WalletTransaction.order_id == Order.id)
        .where(WalletTransaction.user_id == user.id)
        .order_by(WalletTransaction.created_at.desc(), WalletTransaction.id.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = db.execute(stmt).all()
    return [
        BuyerWalletTransactionOut(
            id=tx.id,
            type=tx.type,
            amount=tx.amount,
            status=tx.status,
            order_public_id=order_public_id,
            reference=tx.reference,
            created_at=tx.created_at,
        )
        for tx, order_public_id in rows
    ]


@router.post("/payment-intents", response_model=PaymentIntentOut)
def create_payment_intent(
    payload: PaymentIntentCreateIn,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_api_key),
):
    intent = payment_intent_service.create_payment_intent(
        db,
        user=user,
        amount=payload.amount,
        provider=payload.provider,
        currency=payload.currency,
        idempotency_key=idempotency_key,
    )
    db.commit()
    db.refresh(intent)
    return intent


@router.get("/payment-intents/{public_id}", response_model=PaymentIntentOut)
def get_payment_intent(
    public_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_api_key),
):
    return payment_intent_service.get_user_payment_intent(db, user=user, public_id=public_id)

