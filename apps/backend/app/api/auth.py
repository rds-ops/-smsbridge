from __future__ import annotations
import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.db.session import get_db
from app.models import LoginAttempt, RefreshSession, User, UserLimit, Wallet
from app.schemas.auth import AuthOut, LoginIn, RefreshIn, RegisterIn, TokenOut
from app.schemas.common import UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])
LOGIN_FAILURE_DETAIL = "Invalid email or password"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _ip_hash(request: Request) -> str | None:
    if not request.client or not request.client.host:
        return None
    return hashlib.sha256(request.client.host.encode("utf-8")).hexdigest()


def _user_agent(request: Request) -> str | None:
    value = request.headers.get("user-agent")
    if not value:
        return None
    return value[:255]


def _normalized_login_identifier(value: str) -> str:
    return value.strip().lower()


def _login_identifier_hash(value: str) -> str:
    return hashlib.sha256(_normalized_login_identifier(value).encode("utf-8")).hexdigest()


def _lockout_enabled() -> bool:
    return settings.login_max_failed_attempts > 0 and settings.login_lockout_seconds > 0


def _login_attempt(db: Session, identifier_hash: str) -> LoginAttempt | None:
    stmt = select(LoginAttempt).where(LoginAttempt.identifier_hash == identifier_hash)
    if db.bind and db.bind.dialect.name != "sqlite":
        stmt = stmt.with_for_update()
    return db.scalar(stmt)


def _login_locked(attempt: LoginAttempt | None, now: datetime) -> bool:
    return bool(attempt and attempt.locked_until and _ensure_aware(attempt.locked_until) > now)


def _clear_expired_login_lock(attempt: LoginAttempt | None, now: datetime) -> None:
    if not attempt or not attempt.locked_until:
        return
    if _ensure_aware(attempt.locked_until) <= now:
        attempt.failed_attempts = 0
        attempt.first_failed_at = None
        attempt.last_failed_at = None
        attempt.locked_until = None


def _record_failed_login(
    db: Session,
    identifier_hash: str,
    user: User | None,
    now: datetime,
    attempt: LoginAttempt | None,
) -> None:
    if not _lockout_enabled():
        return
    if not attempt:
        user_id = user.id if user else None
        attempt = LoginAttempt(identifier_hash=identifier_hash, user_id=user_id)
        db.add(attempt)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            attempt = _login_attempt(db, identifier_hash)
            if not attempt:
                return
            if user_id and attempt.user_id is None:
                attempt.user_id = user_id
    elif user and attempt.user_id is None:
        attempt.user_id = user.id

    _clear_expired_login_lock(attempt, now)
    if _login_locked(attempt, now):
        return

    if attempt.failed_attempts == 0:
        attempt.first_failed_at = now
    attempt.failed_attempts += 1
    attempt.last_failed_at = now
    if attempt.failed_attempts >= settings.login_max_failed_attempts:
        attempt.locked_until = now + timedelta(seconds=settings.login_lockout_seconds)


def _reset_successful_login(db: Session, identifier_hash: str, user: User, attempt: LoginAttempt | None) -> None:
    if not _lockout_enabled():
        return
    if not attempt:
        return
    attempt.user_id = user.id
    attempt.failed_attempts = 0
    attempt.first_failed_at = None
    attempt.last_failed_at = None
    attempt.locked_until = None


def _tokens(db: Session, user: User, request: Request) -> TokenOut:
    expires_at = _now() + timedelta(minutes=settings.refresh_token_minutes)
    session = RefreshSession(
        user_id=user.id,
        expires_at=expires_at,
        user_agent=_user_agent(request),
        ip_hash=_ip_hash(request),
    )
    db.add(session)
    db.flush()
    return TokenOut(
        access_token=create_token(str(user.id), settings.access_token_minutes, "access"),
        refresh_token=create_token(str(user.id), settings.refresh_token_minutes, "refresh", jti=session.jti),
    )


@router.post("/register", response_model=AuthOut)
def register(payload: RegisterIn, request: Request, db: Session = Depends(get_db)):
    existing = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing:
        raise HTTPException(status_code=409, detail="Email is already registered")
    user = User(email=payload.email.lower(), password_hash=hash_password(payload.password), locale=payload.locale)
    user.limit = UserLimit()
    user.wallet = Wallet()
    db.add(user)
    db.flush()
    token = _tokens(db, user, request)
    db.commit()
    db.refresh(user)
    return AuthOut(**token.model_dump(), user=UserPublic.model_validate(user))


@router.post("/login", response_model=AuthOut)
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)):
    normalized_email = _normalized_login_identifier(payload.email)
    identifier_hash = _login_identifier_hash(normalized_email)
    now = _now()
    attempt = _login_attempt(db, identifier_hash) if _lockout_enabled() else None
    _clear_expired_login_lock(attempt, now)
    if _login_locked(attempt, now):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=LOGIN_FAILURE_DETAIL)

    user = db.scalar(select(User).where(User.email == normalized_email))
    if not user or not verify_password(payload.password, user.password_hash):
        _record_failed_login(db, identifier_hash, user, now, attempt)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=LOGIN_FAILURE_DETAIL)
    _reset_successful_login(db, identifier_hash, user, attempt)
    token = _tokens(db, user, request)
    db.commit()
    return AuthOut(**token.model_dump(), user=UserPublic.model_validate(user))


@router.post("/refresh", response_model=TokenOut)
def refresh(payload: RefreshIn, db: Session = Depends(get_db)):
    decoded = decode_token(payload.refresh_token)
    if not decoded or decoded.get("typ") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    jti = decoded.get("jti")
    if not jti:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user = db.get(User, int(decoded["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    session = db.scalar(
        select(RefreshSession).where(
            RefreshSession.jti == str(jti),
            RefreshSession.user_id == user.id,
        )
    )
    if not session or session.revoked_at is not None:
        raise HTTPException(status_code=401, detail="Refresh session is revoked")
    if _ensure_aware(session.expires_at) <= _now():
        raise HTTPException(status_code=401, detail="Refresh session is expired")
    session.last_used_at = _now()
    db.commit()
    return TokenOut(
        access_token=create_token(str(user.id), settings.access_token_minutes, "access"),
        refresh_token=payload.refresh_token,
    )


@router.post("/logout")
def logout(payload: RefreshIn, db: Session = Depends(get_db)):
    decoded = decode_token(payload.refresh_token)
    if not decoded or decoded.get("typ") != "refresh" or not decoded.get("jti"):
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    session = db.scalar(select(RefreshSession).where(RefreshSession.jti == str(decoded["jti"])))
    if not session:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if session.revoked_at is None:
        session.revoked_at = _now()
        db.commit()
    return {"status": "ok"}


@router.post("/logout-all")
def logout_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    now = _now()
    sessions = list(
        db.scalars(
            select(RefreshSession).where(
                RefreshSession.user_id == user.id,
                RefreshSession.revoked_at.is_(None),
            )
        )
    )
    for session in sessions:
        session.revoked_at = now
    db.commit()
    return {"status": "ok", "revoked_sessions": len(sessions)}


@router.get("/me", response_model=UserPublic)
def me(user: User = Depends(get_current_user)):
    return user

