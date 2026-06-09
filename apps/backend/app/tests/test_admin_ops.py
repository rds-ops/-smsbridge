from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import ApiRequestLog, Order, PaymentIntent, Provider, Supplier, SupplierPayoutRequest, UserRiskAction


def _provider_id(db) -> int:
    provider = db.scalar(select(Provider).where(Provider.code == "mock"))
    assert provider is not None
    return provider.id


def _add_order(db, *, user_id: int, status: str) -> Order:
    now = datetime.now(timezone.utc)
    order = Order(
        user_id=user_id,
        provider_id=_provider_id(db),
        provider_order_id=f"ops-{user_id}-{status}-{now.timestamp()}",
        service_code="telegram",
        country_iso2="ID",
        phone_number="+10000000000",
        status=status,
        price=Decimal("1.0000"),
        provider_cost=Decimal("0.5000"),
        expires_at=now + timedelta(minutes=15),
        created_at=now,
        updated_at=now,
    )
    db.add(order)
    return order


def test_admin_ops_summary_is_admin_only(client, user_token):
    missing = client.get("/admin/ops/summary")
    user = client.get("/admin/ops/summary", headers={"Authorization": f"Bearer {user_token}"})

    assert missing.status_code == 401
    assert user.status_code == 403


def test_admin_ops_summary_returns_safe_operational_counts(client, admin_token):
    with SessionLocal() as db:
        for status in ["failed", "failed", "failed", "failed", "completed"]:
            _add_order(db, user_id=2, status=status)
        _add_order(db, user_id=2, status="waiting_sms")
        db.add(UserRiskAction(user_id=2, actor_user_id=1, action="watch", note="ops test"))
        db.add(
            ApiRequestLog(
                endpoint="/api/v1/orders",
                method="POST",
                status_code=500,
                user_id=2,
                request_id="ops-500",
            )
        )
        db.add(
            ApiRequestLog(
                endpoint="/api/v1/orders",
                method="POST",
                status_code=429,
                user_id=2,
                request_id="ops-429",
            )
        )
        db.add(
            PaymentIntent(
                user_id=2,
                provider="manual_test",
                currency="USD",
                amount=Decimal("5.0000"),
                status="pending",
                intent_metadata={},
            )
        )
        supplier = Supplier(name="Ops Supplier", email="ops-supplier@example.com", status="active")
        db.add(supplier)
        db.flush()
        db.add(
            SupplierPayoutRequest(
                supplier_id=supplier.id,
                amount=Decimal("2.0000"),
                currency="USD",
                status="requested",
            )
        )
        db.commit()

    response = client.get("/admin/ops/summary", headers={"Authorization": f"Bearer {admin_token}"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    assert body["high_risk_users_count"] == 1
    assert body["watchlisted_users_count"] == 1
    assert body["pending_payment_intents_count"] == 1
    assert body["pending_supplier_payout_requests_count"] == 1
    assert body["active_waiting_sms_orders_count"] == 1
    assert body["recent_5xx_request_count"] == 1
    assert body["recent_rate_limit_429_count"] == 1
    assert "payment_reconciliation_issue_counts" in body
    assert "supplier_payout_reconciliation_issue_counts" in body
    assert "request_id" not in body
    assert "api_key" not in str(body).lower()
    assert "sms_text" not in str(body).lower()
