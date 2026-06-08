from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import generate_api_key, hash_api_key
from app.models import BuyerApiKey, User


def key_prefix(raw_key: str) -> str:
    return raw_key[:16]


def create_buyer_api_key(
    db: Session,
    user: User,
    *,
    name: str | None = None,
    scopes: dict | None = None,
) -> tuple[BuyerApiKey, str]:
    raw = generate_api_key()
    api_key = BuyerApiKey(
        user_id=user.id,
        name=name,
        key_hash=hash_api_key(raw),
        key_prefix=key_prefix(raw),
        status="active",
        scopes=scopes,
    )
    db.add(api_key)
    db.flush()
    return api_key, raw


def list_buyer_api_keys(db: Session, user: User) -> list[BuyerApiKey]:
    return list(
        db.scalars(
            select(BuyerApiKey)
            .where(BuyerApiKey.user_id == user.id)
            .order_by(BuyerApiKey.created_at.desc(), BuyerApiKey.id.desc())
        )
    )


def revoke_buyer_api_key(db: Session, user: User, public_id: str) -> BuyerApiKey:
    api_key = db.scalar(
        select(BuyerApiKey)
        .where(BuyerApiKey.user_id == user.id, BuyerApiKey.public_id == public_id)
        .with_for_update()
    )
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    if api_key.status != "revoked":
        api_key.status = "revoked"
        api_key.revoked_at = datetime.now(timezone.utc)
    db.flush()
    return api_key
