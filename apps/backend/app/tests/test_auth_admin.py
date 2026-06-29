from __future__ import annotations
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_token, decode_token
from app.db.session import SessionLocal
from app.models import AuditLog, RefreshSession, User, WalletTransaction


def test_user_registration_login(client):
    response = client.post("/auth/register", json={"email": "new@example.com", "password": "strong-pass", "locale": "en"})
    assert response.status_code == 200
    assert response.json()["user"]["status"] == "active"

    login = client.post("/auth/login", json={"email": "new@example.com", "password": "strong-pass"})
    assert login.status_code == 200
    assert login.json()["access_token"]


def test_login_creates_refresh_session(client):
    response = client.post("/auth/login", json={"email": "user@smsbridge.local", "password": "change-me"})
    assert response.status_code == 200, response.text
    refresh_token = response.json()["refresh_token"]
    decoded = decode_token(refresh_token)
    assert decoded and decoded["typ"] == "refresh"
    assert decoded.get("jti")

    db = SessionLocal()
    try:
        session = db.scalar(select(RefreshSession).where(RefreshSession.jti == decoded["jti"]))
        assert session is not None
        assert session.user_id == 2
        assert session.revoked_at is None
        assert session.expires_at is not None
        assert session.ip_hash
    finally:
        db.close()


def test_refresh_requires_active_refresh_session_and_updates_last_used(client):
    login = client.post("/auth/login", json={"email": "user@smsbridge.local", "password": "change-me"})
    assert login.status_code == 200, login.text
    refresh_token = login.json()["refresh_token"]

    response = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"] == refresh_token

    decoded = decode_token(refresh_token)
    db = SessionLocal()
    try:
        session = db.scalar(select(RefreshSession).where(RefreshSession.jti == decoded["jti"]))
        assert session is not None
        assert session.last_used_at is not None
    finally:
        db.close()


def test_logout_revokes_current_refresh_session(client):
    login = client.post("/auth/login", json={"email": "user@smsbridge.local", "password": "change-me"})
    refresh_token = login.json()["refresh_token"]

    logout = client.post("/auth/logout", json={"refresh_token": refresh_token})
    assert logout.status_code == 200, logout.text
    assert logout.json()["status"] == "ok"

    refresh = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh.status_code == 401
    assert refresh.json()["detail"] == "Refresh session is revoked"


def test_logout_is_idempotent_for_same_refresh_session(client):
    login = client.post("/auth/login", json={"email": "user@smsbridge.local", "password": "change-me"})
    refresh_token = login.json()["refresh_token"]

    first = client.post("/auth/logout", json={"refresh_token": refresh_token})
    second = client.post("/auth/logout", json={"refresh_token": refresh_token})
    assert first.status_code == 200
    assert second.status_code == 200


def test_logout_all_revokes_only_current_user_sessions(client):
    buyer_login_1 = client.post("/auth/login", json={"email": "user@smsbridge.local", "password": "change-me"}).json()
    buyer_login_2 = client.post("/auth/login", json={"email": "user@smsbridge.local", "password": "change-me"}).json()
    admin_login = client.post("/auth/login", json={"email": "admin@smsbridge.local", "password": "change-me"}).json()

    response = client.post("/auth/logout-all", headers={"Authorization": f"Bearer {buyer_login_1['access_token']}"})
    assert response.status_code == 200, response.text
    assert response.json()["revoked_sessions"] == 2

    buyer_refresh_1 = client.post("/auth/refresh", json={"refresh_token": buyer_login_1["refresh_token"]})
    buyer_refresh_2 = client.post("/auth/refresh", json={"refresh_token": buyer_login_2["refresh_token"]})
    admin_refresh = client.post("/auth/refresh", json={"refresh_token": admin_login["refresh_token"]})
    assert buyer_refresh_1.status_code == 401
    assert buyer_refresh_2.status_code == 401
    assert admin_refresh.status_code == 200


def test_admin_can_revoke_all_refresh_sessions_for_target_user(client):
    buyer_login_1 = client.post("/auth/login", json={"email": "user@smsbridge.local", "password": "change-me"}).json()
    buyer_login_2 = client.post("/auth/login", json={"email": "user@smsbridge.local", "password": "change-me"}).json()
    admin_login = client.post("/auth/login", json={"email": "admin@smsbridge.local", "password": "change-me"}).json()

    response = client.post(
        "/admin/users/2/sessions/revoke-all",
        headers={"Authorization": f"Bearer {admin_login['access_token']}"},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ok", "revoked_sessions": 2}

    buyer_refresh_1 = client.post("/auth/refresh", json={"refresh_token": buyer_login_1["refresh_token"]})
    buyer_refresh_2 = client.post("/auth/refresh", json={"refresh_token": buyer_login_2["refresh_token"]})
    admin_refresh = client.post("/auth/refresh", json={"refresh_token": admin_login["refresh_token"]})
    assert buyer_refresh_1.status_code == 401
    assert buyer_refresh_2.status_code == 401
    assert admin_refresh.status_code == 200

    db = SessionLocal()
    try:
        active_buyer_sessions = list(
            db.scalars(
                select(RefreshSession).where(
                    RefreshSession.user_id == 2,
                    RefreshSession.revoked_at.is_(None),
                )
            )
        )
        audit = db.scalar(
            select(AuditLog).where(
                AuditLog.action == "user.sessions.revoke_all",
                AuditLog.entity_id == "2",
            )
        )
        assert active_buyer_sessions == []
        assert audit is not None
        assert audit.actor_user_id == 1
        assert audit.log_metadata["revoked_sessions"] == 2
    finally:
        db.close()


def test_admin_revoke_user_refresh_sessions_is_idempotent(client):
    buyer_login = client.post("/auth/login", json={"email": "user@smsbridge.local", "password": "change-me"}).json()
    admin_login = client.post("/auth/login", json={"email": "admin@smsbridge.local", "password": "change-me"}).json()
    headers = {"Authorization": f"Bearer {admin_login['access_token']}"}

    first = client.post("/admin/users/2/sessions/revoke-all", headers=headers)
    second = client.post("/admin/users/2/sessions/revoke-all", headers=headers)

    assert first.status_code == 200, first.text
    assert first.json()["revoked_sessions"] == 1
    assert second.status_code == 200, second.text
    assert second.json()["revoked_sessions"] == 0
    refresh = client.post("/auth/refresh", json={"refresh_token": buyer_login["refresh_token"]})
    assert refresh.status_code == 401


def test_non_admin_cannot_revoke_user_refresh_sessions(client, user_token):
    response = client.post(
        "/admin/users/1/sessions/revoke-all",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403


def test_admin_revoke_user_refresh_sessions_missing_user(client, admin_token):
    response = client.post(
        "/admin/users/999999/sessions/revoke-all",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def test_refresh_rejects_expired_refresh_session(client):
    login = client.post("/auth/login", json={"email": "user@smsbridge.local", "password": "change-me"})
    refresh_token = login.json()["refresh_token"]
    decoded = decode_token(refresh_token)

    db = SessionLocal()
    try:
        session = db.scalar(select(RefreshSession).where(RefreshSession.jti == decoded["jti"]))
        session.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()

    response = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 401
    assert response.json()["detail"] == "Refresh session is expired"


def test_refresh_rejects_revoked_refresh_session(client):
    login = client.post("/auth/login", json={"email": "user@smsbridge.local", "password": "change-me"})
    refresh_token = login.json()["refresh_token"]
    decoded = decode_token(refresh_token)

    db = SessionLocal()
    try:
        session = db.scalar(select(RefreshSession).where(RefreshSession.jti == decoded["jti"]))
        session.revoked_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()

    response = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 401
    assert response.json()["detail"] == "Refresh session is revoked"


def test_old_stateless_refresh_token_without_jti_is_rejected(client):
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == "user@smsbridge.local"))
        old_token = create_token(str(user.id), settings.refresh_token_minutes, "refresh")
    finally:
        db.close()

    response = client.post("/auth/refresh", json={"refresh_token": old_token})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid refresh token"


def test_admin_login_seed_account(client):
    response = client.post("/auth/login", json={"email": "admin@smsbridge.local", "password": "change-me"})
    assert response.status_code == 200, response.text
    assert response.json()["user"]["role"] == "admin"


def test_admin_manual_deposit(client, admin_token):
    response = client.post(
        "/admin/wallets/deposit",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"user_id": 2, "amount": "10.00", "reference": "manual-test"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["balance"] == "35.0000"
    db = SessionLocal()
    try:
        tx = db.scalar(select(WalletTransaction).where(WalletTransaction.type == "deposit", WalletTransaction.user_id == 2))
        audit = db.scalar(select(AuditLog).where(AuditLog.action == "wallet.deposit", AuditLog.entity_id == "2"))
        assert tx is not None
        assert audit is not None
    finally:
        db.close()


def test_normal_user_cannot_call_admin_deposit(client, user_token):
    response = client.post(
        "/admin/wallets/deposit",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"user_id": 2, "amount": "10.00"},
    )
    assert response.status_code == 403


def test_admin_deposit_requires_valid_token(client):
    missing = client.post("/admin/wallets/deposit", json={"user_id": 2, "amount": "10.00"})
    assert missing.status_code == 401

    invalid = client.post(
        "/admin/wallets/deposit",
        headers={"Authorization": "Bearer not-a-real-token"},
        json={"user_id": 2, "amount": "10.00"},
    )
    assert invalid.status_code == 401
    assert invalid.json()["detail"] == "Invalid token"


def test_admin_can_update_user_limits(client, admin_token):
    response = client.patch(
        "/admin/users/2/limits",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"max_orders_per_day": 50, "max_daily_spend": "100.00", "tier": "verified"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tier"] == "verified"
    assert body["limit"]["max_orders_per_day"] == 50


def test_admin_metrics_return_basic_values(client, admin_token):
    response = client.get("/admin/metrics", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    assert response.json()["total_users"] == 2
