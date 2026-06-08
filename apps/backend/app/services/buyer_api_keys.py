from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import generate_api_key, hash_api_key
from app.models import ApiRequestLog, BuyerApiKey, User

DEFAULT_BUYER_API_KEY_SCOPES = [
    "read",
    "wallet:read",
    "orders:create",
    "orders:read",
    "orders:cancel",
    "orders:finish",
    "payments:create",
    "payments:read",
]


def key_prefix(raw_key: str) -> str:
    return raw_key[:16]


def normalize_scopes(scopes: list[str] | None) -> list[str]:
    if not scopes:
        return list(DEFAULT_BUYER_API_KEY_SCOPES)
    normalized: list[str] = []
    for scope in scopes:
        scope_value = str(scope).strip()
        if scope_value and scope_value not in normalized:
            normalized.append(scope_value)
    return normalized or list(DEFAULT_BUYER_API_KEY_SCOPES)


def create_buyer_api_key(
    db: Session,
    user: User,
    *,
    name: str | None = None,
    scopes: list[str] | None = None,
) -> tuple[BuyerApiKey, str]:
    raw = generate_api_key()
    api_key = BuyerApiKey(
        user_id=user.id,
        name=name,
        key_hash=hash_api_key(raw),
        key_prefix=key_prefix(raw),
        status="active",
        scopes=normalize_scopes(scopes),
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


def get_buyer_api_key_usage(db: Session, user: User, public_id: str) -> dict:
    api_key = db.scalar(select(BuyerApiKey).where(BuyerApiKey.user_id == user.id, BuyerApiKey.public_id == public_id))
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    total = int(
        db.scalar(select(func.count(ApiRequestLog.id)).where(ApiRequestLog.buyer_api_key_id == api_key.id))
        or 0
    )
    rows = db.execute(
        select(
            ApiRequestLog.endpoint,
            ApiRequestLog.method,
            ApiRequestLog.status_code,
            func.count(ApiRequestLog.id).label("count"),
        )
        .where(ApiRequestLog.buyer_api_key_id == api_key.id)
        .group_by(ApiRequestLog.endpoint, ApiRequestLog.method, ApiRequestLog.status_code)
        .order_by(func.count(ApiRequestLog.id).desc(), ApiRequestLog.endpoint.asc())
        .limit(100)
    ).all()
    return {
        "public_id": api_key.public_id,
        "key_prefix": api_key.key_prefix,
        "status": api_key.status,
        "total_requests": total,
        "last_used_at": api_key.last_used_at,
        "recent": [
            {
                "endpoint": endpoint,
                "method": method,
                "status_code": status_code,
                "count": count,
            }
            for endpoint, method, status_code, count in rows
        ],
    }
