from __future__ import annotations
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_token, hash_api_key
from app.db.session import get_db
from app.models import BuyerApiKey, Supplier, User

bearer_scheme = HTTPBearer(auto_error=False)

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


def _remember_user(request: Request, user: User) -> User:
    request.state.user_id = user.id
    return user


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    payload = decode_token(credentials.credentials)
    if not payload or payload.get("typ") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.get(User, int(payload["sub"]))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    request.state.auth_type = "jwt"
    return _remember_user(request, user)


def _managed_key_scopes(managed_key: BuyerApiKey) -> list[str]:
    scopes = managed_key.scopes
    if not scopes:
        return list(DEFAULT_BUYER_API_KEY_SCOPES)
    if isinstance(scopes, list):
        return [str(scope) for scope in scopes]
    return list(DEFAULT_BUYER_API_KEY_SCOPES)


def _has_scope(scopes: list[str], required_scope: str) -> bool:
    return required_scope in scopes or (required_scope.endswith(":read") and "read" in scopes)


def _authenticate_user_or_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
    db: Session,
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = credentials.credentials
    payload = decode_token(token)
    if payload and payload.get("typ") == "access":
        user = db.get(User, int(payload["sub"]))
        if user:
            request.state.auth_type = "jwt"
            return _remember_user(request, user)

    token_hash = hash_api_key(token)
    managed_key = db.scalar(
        select(BuyerApiKey).where(
            BuyerApiKey.key_hash == token_hash,
            BuyerApiKey.status == "active",
        )
    )
    if managed_key:
        managed_key.last_used_at = datetime.now(timezone.utc)
        db.commit()
        user = db.get(User, managed_key.user_id)
        if user:
            request.state.auth_type = "managed_buyer_api_key"
            request.state.buyer_api_key_id = managed_key.id
            request.state.buyer_api_key_scopes = _managed_key_scopes(managed_key)
            return _remember_user(request, user)

    user = db.scalar(select(User).where(User.api_key_hash == token_hash))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token or API key")
    request.state.auth_type = "legacy_buyer_api_key"
    return _remember_user(request, user)


def get_current_user_or_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    return _authenticate_user_or_api_key(request, credentials, db)


def require_buyer_scope(required_scope: str):
    def dependency(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
        db: Session = Depends(get_db),
    ) -> User:
        user = _authenticate_user_or_api_key(request, credentials, db)
        if getattr(request.state, "auth_type", None) == "managed_buyer_api_key":
            scopes = getattr(request.state, "buyer_api_key_scopes", [])
            if not _has_scope(scopes, required_scope):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API key scope is not allowed")
        return user

    return dependency


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def get_current_supplier(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Supplier:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    supplier = db.scalar(select(Supplier).where(Supplier.api_key_hash == hash_api_key(credentials.credentials)))
    if not supplier:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid supplier API key")
    request.state.supplier_id = supplier.id
    return supplier


def require_active_supplier(supplier: Supplier = Depends(get_current_supplier)) -> Supplier:
    if supplier.status == "blocked":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Supplier is blocked")
    if supplier.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Supplier is not active")
    return supplier
