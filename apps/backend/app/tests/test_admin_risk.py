from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import ApiRequestLog, BuyerApiKey, Order, Provider, UserRiskAction


def _provider_id(db) -> int:
    provider = db.scalar(select(Provider).where(Provider.code == "mock"))
    assert provider is not None
    return provider.id


def _add_order(db, *, user_id: int, status: str, created_at: datetime | None = None) -> Order:
    created_at = created_at or datetime.now(timezone.utc)
    order = Order(
        user_id=user_id,
        provider_id=_provider_id(db),
        provider_order_id=f"risk-{user_id}-{status}-{created_at.timestamp()}",
        service_code="telegram",
        country_iso2="ID",
        operator=None,
        phone_number="+10000000000",
        status=status,
        price=Decimal("1.0000"),
        provider_cost=Decimal("0.5000"),
        expires_at=created_at + timedelta(minutes=15),
        created_at=created_at,
        updated_at=created_at,
    )
    db.add(order)
    return order


def test_low_risk_user_summary(client, admin_token):
    response = client.get("/admin/risk/users/2", headers={"Authorization": f"Bearer {admin_token}"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user_id"] == 2
    assert body["risk_level"] == "low"
    assert body["total_orders"] == 0
    assert body["managed_api_key_count"] == 0
    assert body["watchlisted"] is False
    assert body["last_reviewed_at"] is None
    assert body["latest_note"] is None
    assert "api_key" not in body
    assert "key_hash" not in body


def test_high_cancellation_expiration_user_becomes_high_risk(client, admin_token):
    with SessionLocal() as db:
        for status in ["expired", "expired", "expired", "cancelled", "completed", "completed"]:
            _add_order(db, user_id=2, status=status)
        db.commit()

    response = client.get("/admin/risk/users/2", headers={"Authorization": f"Bearer {admin_token}"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["risk_level"] == "high"
    assert body["total_orders"] == 6
    assert body["expired_orders"] == 3
    assert body["cancelled_orders"] == 1
    assert body["completed_orders"] == 2
    assert body["expiration_rate"] == 0.5


def test_high_recent_order_burst_becomes_high_risk(client, admin_token):
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        for idx in range(21):
            _add_order(db, user_id=2, status="waiting_sms", created_at=now - timedelta(minutes=idx))
        db.commit()

    response = client.get("/admin/risk/users/2", headers={"Authorization": f"Bearer {admin_token}"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["risk_level"] == "high"
    assert body["orders_last_1h"] == 21
    assert body["active_orders"] == 21


def test_risk_list_filters_and_sorts_by_riskiest(client, admin_token):
    with SessionLocal() as db:
        for status in ["failed", "failed", "failed", "failed", "completed"]:
            _add_order(db, user_id=2, status=status)
        db.commit()

    response = client.get("/admin/risk/users?risk_level=high", headers={"Authorization": f"Bearer {admin_token}"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body
    assert body[0]["user_id"] == 2
    assert all(row["risk_level"] == "high" for row in body)


def test_risk_summary_includes_api_request_and_key_counts_without_secrets(client, admin_token, user_token):
    created = client.post(
        "/api/v1/api-keys",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"name": "risk key", "scopes": ["wallet:read"]},
    )
    assert created.status_code == 200, created.text
    raw_key = created.json()["api_key"]
    revoked = client.post(
        f"/api/v1/api-keys/{created.json()['public_id']}/revoke",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert revoked.status_code == 200, revoked.text

    with SessionLocal() as db:
        db.add(ApiRequestLog(user_id=2, endpoint="/api/v1/balance", method="GET", status_code=200))
        db.commit()

    response = client.get("/admin/risk/users/2", headers={"Authorization": f"Bearer {admin_token}"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["api_requests_last_1h"] >= 1
    assert body["managed_api_key_count"] == 1
    assert body["revoked_api_key_count"] == 1
    assert raw_key not in str(body)
    assert "key_hash" not in str(body)

    with SessionLocal() as db:
        stored = db.scalar(select(BuyerApiKey).where(BuyerApiKey.public_id == created.json()["public_id"]))
        assert stored is not None
        assert stored.key_hash not in str(body)


def test_admin_risk_endpoints_are_admin_only(client, user_token):
    user_response = client.get("/admin/risk/users", headers={"Authorization": f"Bearer {user_token}"})
    missing_response = client.get("/admin/risk/users")

    assert user_response.status_code == 403
    assert missing_response.status_code == 401


def test_admin_can_add_watch_note_and_clear_watch_actions(client, admin_token):
    watch = client.post(
        "/admin/risk/users/2/actions",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"action": "watch", "note": "Burst ordering pattern needs manual review"},
    )
    assert watch.status_code == 200, watch.text
    assert watch.json()["action"] == "watch"
    assert watch.json()["actor_user_id"] == 1

    summary = client.get("/admin/risk/users/2", headers={"Authorization": f"Bearer {admin_token}"})
    assert summary.status_code == 200, summary.text
    assert summary.json()["watchlisted"] is True
    assert summary.json()["latest_note"] == "Burst ordering pattern needs manual review"

    note = client.post(
        "/admin/risk/users/2/actions",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"action": "note", "note": "Buyer replied to support"},
    )
    assert note.status_code == 200, note.text

    reviewed = client.post(
        "/admin/risk/users/2/actions",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"action": "mark_reviewed"},
    )
    assert reviewed.status_code == 200, reviewed.text

    clear = client.post(
        "/admin/risk/users/2/actions",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"action": "clear_watch", "note": "Manual review cleared"},
    )
    assert clear.status_code == 200, clear.text

    actions = client.get("/admin/risk/users/2/actions", headers={"Authorization": f"Bearer {admin_token}"})
    assert actions.status_code == 200, actions.text
    assert [row["action"] for row in actions.json()] == ["clear_watch", "mark_reviewed", "note", "watch"]

    summary_after_clear = client.get("/admin/risk/users/2", headers={"Authorization": f"Bearer {admin_token}"})
    assert summary_after_clear.status_code == 200, summary_after_clear.text
    assert summary_after_clear.json()["watchlisted"] is False
    assert summary_after_clear.json()["last_reviewed_at"] is not None
    assert summary_after_clear.json()["latest_note"] == "Manual review cleared"


def test_risk_action_validation_and_note_safety(client, admin_token):
    invalid_action = client.post(
        "/admin/risk/users/2/actions",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"action": "block", "note": "not supported"},
    )
    assert invalid_action.status_code == 422

    too_long = client.post(
        "/admin/risk/users/2/actions",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"action": "note", "note": "x" * 1001},
    )
    assert too_long.status_code == 422

    secret_note = client.post(
        "/admin/risk/users/2/actions",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"action": "note", "note": "Authorization: Bearer sb_live_secret"},
    )
    assert secret_note.status_code == 400
    assert secret_note.json()["detail"] == "Risk note must not contain secrets or API keys"

    with SessionLocal() as db:
        assert db.scalar(select(UserRiskAction).where(UserRiskAction.user_id == 2)) is None


def test_risk_action_endpoints_are_admin_only(client, user_token):
    user_post = client.post(
        "/admin/risk/users/2/actions",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"action": "watch"},
    )
    user_get = client.get("/admin/risk/users/2/actions", headers={"Authorization": f"Bearer {user_token}"})

    assert user_post.status_code == 403
    assert user_get.status_code == 403
