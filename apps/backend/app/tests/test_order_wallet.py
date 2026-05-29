from __future__ import annotations
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.jobs.tasks import poll_waiting_orders
from app.models import Order, Provider, Price, SmsMessage, User, WalletTransaction
from decimal import Decimal

from app.services import orders as order_service
from app.providers.router import final_price


def create_order(client, user_token):
    response = client.post(
        "/api/v1/orders",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"service_code": "telegram", "country_iso2": "ID"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def count_rows(model, *criteria) -> int:
    db = SessionLocal()
    try:
        return db.scalar(select(func.count(model.id)).where(*criteria))
    finally:
        db.close()


def test_buying_number_creates_order_and_wallet_hold(client, user_token):
    order = create_order(client, user_token)
    assert order["status"] == "waiting_sms"
    balance = client.get("/api/v1/balance", headers={"Authorization": f"Bearer {user_token}"}).json()
    assert balance["balance"] < "25.0000"
    assert balance["held_balance"] > "0.0000"


def test_sms_received_changes_status_to_sms_received(client, user_token):
    order = create_order(client, user_token)
    processed = poll_waiting_orders()
    assert processed >= 1
    response = client.get(f"/api/v1/orders/{order['public_id']}", headers={"Authorization": f"Bearer {user_token}"})
    assert response.json()["status"] == "sms_received"
    assert response.json()["sms_code"]
    db = SessionLocal()
    try:
        entity = db.scalar(select(Order).where(Order.public_id == order["public_id"]))
        messages = list(db.scalars(select(SmsMessage).where(SmsMessage.order_id == entity.id)))
        assert len(messages) == 1
        assert messages[0].provider_id == entity.provider_id
        assert messages[0].source == "external_provider"
        assert messages[0].text == entity.sms_text
        assert messages[0].parsed_code == entity.sms_code
    finally:
        db.close()


def test_external_provider_polling_does_not_duplicate_sms_messages(client, user_token):
    order = create_order(client, user_token)
    assert poll_waiting_orders() >= 1
    assert poll_waiting_orders() == 0
    db = SessionLocal()
    try:
        entity = db.scalar(select(Order).where(Order.public_id == order["public_id"]))
        messages = list(db.scalars(select(SmsMessage).where(SmsMessage.order_id == entity.id)))
        assert len(messages) == 1
        assert messages[0].text == entity.sms_text
        assert messages[0].parsed_code == entity.sms_code
    finally:
        db.close()


def test_finish_order_captures_hold(client, user_token):
    order = create_order(client, user_token)
    poll_waiting_orders()
    response = client.post(f"/api/v1/orders/{order['public_id']}/finish", headers={"Authorization": f"Bearer {user_token}"})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "completed"
    balance = client.get("/api/v1/balance", headers={"Authorization": f"Bearer {user_token}"}).json()
    assert balance["held_balance"] == "0.0000"


def test_cancel_order_refunds_hold(client, user_token):
    order = create_order(client, user_token)
    response = client.post(f"/api/v1/orders/{order['public_id']}/cancel", headers={"Authorization": f"Bearer {user_token}"})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "cancelled"
    balance = client.get("/api/v1/balance", headers={"Authorization": f"Bearer {user_token}"}).json()
    assert balance["balance"] == "25.0000"
    assert balance["held_balance"] == "0.0000"


def test_expired_order_refunds_hold(client, user_token):
    order = create_order(client, user_token)
    db = SessionLocal()
    try:
        entity = db.scalar(select(Order).where(Order.public_id == order["public_id"]))
        entity.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    finally:
        db.close()
    assert poll_waiting_orders() >= 1
    assert poll_waiting_orders() == 0
    balance = client.get("/api/v1/balance", headers={"Authorization": f"Bearer {user_token}"}).json()
    assert balance["balance"] == "25.0000"
    assert balance["held_balance"] == "0.0000"
    db = SessionLocal()
    try:
        entity = db.scalar(select(Order).where(Order.public_id == order["public_id"]))
        refunds = db.scalar(
            select(func.count(WalletTransaction.id)).where(
                WalletTransaction.order_id == entity.id,
                WalletTransaction.type == "refund",
            )
        )
        assert refunds == 1
    finally:
        db.close()


def test_blocked_user_cannot_create_order(client, admin_token, user_token):
    client.patch("/admin/users/2/status", headers={"Authorization": f"Bearer {admin_token}"}, json={"status": "blocked"})
    response = client.post(
        "/api/v1/orders",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"service_code": "telegram", "country_iso2": "ID"},
    )
    assert response.status_code == 403


def test_user_cannot_exceed_limits(client, admin_token, user_token):
    client.patch(
        "/admin/users/2/limits",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"max_orders_per_day": 1, "max_daily_spend": "100.00"},
    )
    assert client.post(
        "/api/v1/orders",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"service_code": "telegram", "country_iso2": "ID"},
    ).status_code == 200
    response = client.post(
        "/api/v1/orders",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"service_code": "telegram", "country_iso2": "ID"},
    )
    assert response.status_code == 429


def test_balance_cannot_go_negative(client, admin_token):
    response = client.post(
        "/admin/wallets/adjustment",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"user_id": 2, "amount": "-100.00", "reference": "bad"},
    )
    assert response.status_code == 400


def test_api_key_auth_works(client, user_token):
    created = client.post("/api/v1/api-key/regenerate", headers={"Authorization": f"Bearer {user_token}"})
    api_key = created.json()["api_key"]
    headers = {"Authorization": f"Bearer {api_key}"}
    response = client.get("/api/v1/balance", headers=headers)
    assert response.status_code == 200
    assert response.json()["currency"] == "USD"
    prices = client.get("/api/v1/prices?service_code=telegram&country_iso2=ID", headers=headers)
    assert prices.status_code == 200
    price = prices.json()[0]
    assert "final_price" in price
    assert "provider_cost" not in price
    order = client.post("/api/v1/orders", headers=headers, json={"service_code": "telegram", "country_iso2": "ID"})
    assert order.status_code == 200, order.text
    fetched = client.get(f"/api/v1/orders/{order.json()['public_id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["public_id"] == order.json()["public_id"]


def test_buying_mock_number_with_deposited_balance(client, admin_token):
    registered = client.post("/auth/register", json={"email": "buyer@example.com", "password": "strong-pass", "locale": "en"})
    token = registered.json()["access_token"]
    deposit_response = client.post(
        "/admin/wallets/deposit",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"user_id": registered.json()["user"]["id"], "amount": "5.00", "reference": "test-deposit"},
    )
    assert deposit_response.status_code == 200
    order = client.post(
        "/api/v1/orders",
        headers={"Authorization": f"Bearer {token}"},
        json={"service_code": "telegram", "country_iso2": "ID"},
    )
    assert order.status_code == 200, order.text
    assert order.json()["status"] == "waiting_sms"


def test_order_create_idempotency_replays_same_order_without_extra_hold(client, user_token):
    headers = {"Authorization": f"Bearer {user_token}", "Idempotency-Key": "order-retry-1"}
    payload = {"service_code": "telegram", "country_iso2": "ID"}

    first = client.post("/api/v1/orders", headers=headers, json=payload)
    assert first.status_code == 200, first.text
    order_count = count_rows(Order, Order.user_id == 2)
    hold_count = count_rows(WalletTransaction, WalletTransaction.user_id == 2, WalletTransaction.type == "hold")
    balance = client.get("/api/v1/balance", headers={"Authorization": f"Bearer {user_token}"}).json()

    second = client.post("/api/v1/orders", headers=headers, json=payload)

    assert second.status_code == 200, second.text
    assert second.json()["public_id"] == first.json()["public_id"]
    assert count_rows(Order, Order.user_id == 2) == order_count
    assert count_rows(WalletTransaction, WalletTransaction.user_id == 2, WalletTransaction.type == "hold") == hold_count
    assert client.get("/api/v1/balance", headers={"Authorization": f"Bearer {user_token}"}).json() == balance


def test_order_create_idempotency_conflicts_on_different_body(client, user_token):
    headers = {"Authorization": f"Bearer {user_token}", "Idempotency-Key": "order-retry-conflict"}
    first = client.post("/api/v1/orders", headers=headers, json={"service_code": "telegram", "country_iso2": "ID"})
    assert first.status_code == 200, first.text
    order_count = count_rows(Order, Order.user_id == 2)

    second = client.post("/api/v1/orders", headers=headers, json={"service_code": "telegram", "country_iso2": "US"})

    assert second.status_code == 409
    assert count_rows(Order, Order.user_id == 2) == order_count


def test_order_create_idempotency_key_is_scoped_per_user(client, admin_token, user_token):
    key = "shared-buyer-key"
    first = client.post(
        "/api/v1/orders",
        headers={"Authorization": f"Bearer {user_token}", "Idempotency-Key": key},
        json={"service_code": "telegram", "country_iso2": "ID"},
    )
    assert first.status_code == 200, first.text

    registered = client.post("/auth/register", json={"email": "second-buyer@example.com", "password": "strong-pass", "locale": "en"})
    assert registered.status_code == 200, registered.text
    second_user_id = registered.json()["user"]["id"]
    second_token = registered.json()["access_token"]
    deposit_response = client.post(
        "/admin/wallets/deposit",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"user_id": second_user_id, "amount": "5.00", "reference": "idempotency-test"},
    )
    assert deposit_response.status_code == 200, deposit_response.text

    second = client.post(
        "/api/v1/orders",
        headers={"Authorization": f"Bearer {second_token}", "Idempotency-Key": key},
        json={"service_code": "telegram", "country_iso2": "ID"},
    )

    assert second.status_code == 200, second.text
    assert second.json()["public_id"] != first.json()["public_id"]


def test_order_create_without_idempotency_key_keeps_existing_behavior(client, user_token):
    headers = {"Authorization": f"Bearer {user_token}"}
    payload = {"service_code": "telegram", "country_iso2": "ID"}

    first = client.post("/api/v1/orders", headers=headers, json=payload)
    second = client.post("/api/v1/orders", headers=headers, json=payload)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert second.json()["public_id"] != first.json()["public_id"]


def test_insufficient_balance_does_not_call_provider_reservation(client, user_token, monkeypatch):
    db = SessionLocal()
    try:
        user = db.get(User, 2)
        user.wallet.balance = Decimal("0.0000")
        db.commit()
    finally:
        db.close()

    def fail_if_called(provider):
        raise AssertionError("provider reservation should not be called")

    monkeypatch.setattr(order_service, "get_adapter", fail_if_called)

    response = client.post(
        "/api/v1/orders",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"service_code": "telegram", "country_iso2": "ID"},
    )

    assert response.status_code == 402
    balance = client.get("/api/v1/balance", headers={"Authorization": f"Bearer {user_token}"}).json()
    assert balance["balance"] == "0.0000"
    assert balance["held_balance"] == "0.0000"


def test_provider_failure_after_hold_refunds_and_marks_order_failed(client, user_token):
    db = SessionLocal()
    try:
        provider = db.scalar(select(Provider).where(Provider.code == "mock"))
        provider.code = "mock_fail_all"
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/api/v1/orders",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"service_code": "telegram", "country_iso2": "ID"},
    )

    assert response.status_code == 502
    balance = client.get("/api/v1/balance", headers={"Authorization": f"Bearer {user_token}"}).json()
    assert balance["balance"] == "25.0000"
    assert balance["held_balance"] == "0.0000"
    assert count_rows(Order, Order.user_id == 2, Order.status == "waiting_sms") == 0
    assert count_rows(WalletTransaction, WalletTransaction.user_id == 2, WalletTransaction.type == "hold") == 0


def test_provider_failure_after_hold_records_refund_if_transaction_is_committed():
    db = SessionLocal()
    try:
        user = db.get(User, 2)
        provider = db.scalar(select(Provider).where(Provider.code == "mock"))
        provider.code = "mock_fail_all"
        db.flush()

        try:
            order_service.create_order(db, user, "telegram", "ID")
        except HTTPException as exc:
            assert exc.status_code == 502
        else:
            raise AssertionError("provider failure should raise")

        db.commit()
        db.refresh(user.wallet)
        assert user.wallet.balance == Decimal("25.0000")
        assert user.wallet.held_balance == Decimal("0.0000")
        failed_order = db.scalar(select(Order).where(Order.user_id == user.id, Order.status == "failed"))
        assert failed_order is not None
        assert db.scalar(
            select(func.count(WalletTransaction.id)).where(
                WalletTransaction.order_id == failed_order.id,
                WalletTransaction.type == "hold",
            )
        ) == 1
        assert db.scalar(
            select(func.count(WalletTransaction.id)).where(
                WalletTransaction.order_id == failed_order.id,
                WalletTransaction.type == "refund",
            )
        ) == 1
    finally:
        db.close()


def test_successful_provider_reservation_creates_exactly_one_hold(client, user_token):
    response = client.post(
        "/api/v1/orders",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"service_code": "telegram", "country_iso2": "ID"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "waiting_sms"
    assert response.json()["phone_number"]
    assert count_rows(Order, Order.user_id == 2) == 1
    assert count_rows(WalletTransaction, WalletTransaction.user_id == 2, WalletTransaction.type == "hold") == 1


def test_provider_fallback_works_with_mock_provider(client, user_token):
    db = SessionLocal()
    try:
        failing = Provider(name="Failing Mock", code="mock_fail", type="mock", status="active", priority=200)
        db.add(failing)
        db.flush()
        db.add(
            Price(
                provider_id=failing.id,
                service_code="telegram",
                country_iso2="ID",
                provider_cost=Decimal("0.10"),
                final_price=final_price(Decimal("0.10"), failing.default_markup_percent),
                available_count=10,
                delivery_rate="50",
            )
        )
        db.commit()
    finally:
        db.close()
    order = create_order(client, user_token)
    assert order["phone_number"].startswith("+62")
