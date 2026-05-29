from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_current_user_or_api_key
from app.core.security import generate_api_key, hash_api_key
from app.db.session import get_db
from app.models import Country, Order, Price, Service, User
from app.schemas.common import (
    BuyerPriceOut,
    CountryOut,
    MessageOut,
    OrderCreate,
    OrderOut,
    ServiceOut,
    UserLimitOut,
    WalletOut,
)
from app.services import orders as order_service

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
def create_order(payload: OrderCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user_or_api_key)):
    order = order_service.create_order(db, user, payload.service_code, payload.country_iso2, payload.operator)
    db.commit()
    db.refresh(order)
    return order


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
    order = order_service.cancel_order(db, order)
    db.commit()
    db.refresh(order)
    return order


@router.post("/orders/{public_id}/finish", response_model=OrderOut)
def finish_order(public_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user_or_api_key)):
    order = order_service.get_user_order(db, user, public_id)
    order = order_service.finish_order(db, order)
    db.commit()
    db.refresh(order)
    return order


@router.post("/api-key/regenerate")
def regenerate_api_key(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    raw = generate_api_key()
    user.api_key_hash = hash_api_key(raw)
    db.commit()
    return {"api_key": raw, "message": "Store this key now. It will not be shown again."}


@router.get("/limits", response_model=UserLimitOut)
def limits(user: User = Depends(get_current_user_or_api_key)):
    if not user.limit:
        raise HTTPException(status_code=404, detail="Limits not configured")
    return user.limit

