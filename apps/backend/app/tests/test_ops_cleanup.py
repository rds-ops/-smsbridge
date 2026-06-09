from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import (
    ApiRequestLog,
    Order,
    PaymentWebhookEvent,
    Provider,
    Supplier,
    SupplierActivation,
    SupplierReleaseRetry,
    SupplierTransaction,
    WalletTransaction,
)
from app.services.ops_cleanup import cleanup_expired_operational_records


def _provider_id(db) -> int:
    provider = db.scalar(select(Provider).where(Provider.code == "mock"))
    assert provider is not None
    return provider.id


def _add_order(db, *, created_at: datetime) -> Order:
    order = Order(
        user_id=2,
        provider_id=_provider_id(db),
        provider_order_id=f"cleanup-order-{created_at.timestamp()}",
        service_code="telegram",
        country_iso2="ID",
        phone_number="+10000000000",
        status="completed",
        price=Decimal("1.0000"),
        provider_cost=Decimal("0.5000"),
        expires_at=created_at + timedelta(minutes=15),
        created_at=created_at,
        updated_at=created_at,
    )
    db.add(order)
    db.flush()
    return order


def _add_supplier_retry(db, *, status: str, updated_at: datetime) -> SupplierReleaseRetry:
    supplier = Supplier(name=f"Cleanup Supplier {status}", email=f"cleanup-{status}@example.com", status="active")
    db.add(supplier)
    db.flush()
    order = _add_order(db, created_at=updated_at)
    activation = SupplierActivation(
        supplier_id=supplier.id,
        order_id=order.id,
        supplier_activation_id=f"cleanup-act-{status}",
        phone_number="+10000000001",
        service_code="telegram",
        country_iso2="ID",
        status="cancelled",
        client_price=Decimal("1.0000"),
        supplier_reward=Decimal("0.7000"),
        created_at=updated_at,
        updated_at=updated_at,
    )
    db.add(activation)
    db.flush()
    retry = SupplierReleaseRetry(
        supplier_activation_id=activation.id,
        supplier_id=supplier.id,
        order_id=order.id,
        retry_type="release",
        status=status,
        reason="cancelled",
        attempt_count=1,
        next_retry_at=updated_at,
        created_at=updated_at,
        updated_at=updated_at,
    )
    db.add(retry)
    return retry


def _seed_cleanup_rows(db):
    now = datetime.now(timezone.utc)
    old_api = now - timedelta(days=91)
    old_operational = now - timedelta(days=181)
    protected_old = now - timedelta(days=365)

    order = _add_order(db, created_at=protected_old)
    db.add(
        WalletTransaction(
            user_id=2,
            order_id=order.id,
            type="capture",
            amount=Decimal("1.0000"),
            status="completed",
            reference="cleanup-protected-wallet",
            created_at=protected_old,
        )
    )
    supplier = Supplier(name="Protected Supplier", email="protected-supplier@example.com", status="active")
    db.add(supplier)
    db.flush()
    db.add(
        SupplierTransaction(
            supplier_id=supplier.id,
            order_id=order.id,
            type="reward",
            amount=Decimal("0.7000"),
            status="completed",
            reference="cleanup-protected-supplier",
            created_at=protected_old,
        )
    )
    db.add(
        ApiRequestLog(
            user_id=2,
            endpoint="/api/v1/balance",
            method="GET",
            status_code=200,
            request_id="old-api-log",
            created_at=old_api,
        )
    )
    db.add(
        PaymentWebhookEvent(
            provider="manual_test",
            external_event_id="cleanup-old-event",
            payload_hash="cleanup-old-hash",
            status="processed",
            created_at=old_operational,
        )
    )
    _add_supplier_retry(db, status="succeeded", updated_at=old_operational)
    _add_supplier_retry(db, status="dead", updated_at=old_operational)
    _add_supplier_retry(db, status="pending", updated_at=old_operational)
    db.commit()


def test_cleanup_dry_run_returns_counts_without_deleting():
    with SessionLocal() as db:
        _seed_cleanup_rows(db)

        result = cleanup_expired_operational_records(db, dry_run=True)
        db.commit()

        assert result.dry_run is True
        assert result.api_request_logs == 1
        assert result.payment_webhook_events == 1
        assert result.supplier_release_retries == 2
        assert result.total == 4
        assert db.scalar(select(func.count(ApiRequestLog.id))) == 1
        assert db.scalar(select(func.count(PaymentWebhookEvent.id))) == 1
        assert db.scalar(select(func.count(SupplierReleaseRetry.id))) == 3


def test_cleanup_deletes_only_expired_operational_records():
    with SessionLocal() as db:
        _seed_cleanup_rows(db)

        result = cleanup_expired_operational_records(db, dry_run=False)
        db.commit()

        assert result.api_request_logs == 1
        assert result.payment_webhook_events == 1
        assert result.supplier_release_retries == 2
        assert db.scalar(select(func.count(ApiRequestLog.id))) == 0
        assert db.scalar(select(func.count(PaymentWebhookEvent.id))) == 0
        assert db.scalar(select(func.count(SupplierReleaseRetry.id))) == 1
        pending_retry = db.scalar(select(SupplierReleaseRetry).where(SupplierReleaseRetry.status == "pending"))
        assert pending_retry is not None
        assert db.scalar(select(func.count(Order.id))) >= 1
        assert db.scalar(select(func.count(WalletTransaction.id))) == 1
        assert db.scalar(select(func.count(SupplierTransaction.id))) == 1


def test_admin_cleanup_dry_run_is_admin_only(client, user_token):
    missing = client.post("/admin/ops/cleanup/dry-run")
    user = client.post("/admin/ops/cleanup/dry-run", headers={"Authorization": f"Bearer {user_token}"})

    assert missing.status_code == 401
    assert user.status_code == 403


def test_admin_cleanup_dry_run_returns_counts_and_does_not_delete(client, admin_token):
    with SessionLocal() as db:
        _seed_cleanup_rows(db)

    response = client.post("/admin/ops/cleanup/dry-run", headers={"Authorization": f"Bearer {admin_token}"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {
        "api_request_logs": 1,
        "payment_webhook_events": 1,
        "supplier_release_retries": 2,
        "total": 4,
        "dry_run": True,
    }
    with SessionLocal() as db:
        assert db.scalar(select(func.count(ApiRequestLog.id)).where(ApiRequestLog.request_id == "old-api-log")) == 1
        assert db.scalar(select(func.count(PaymentWebhookEvent.id))) == 1
        assert db.scalar(select(func.count(SupplierReleaseRetry.id))) == 3
