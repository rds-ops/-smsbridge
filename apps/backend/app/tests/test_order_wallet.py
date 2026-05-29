from __future__ import annotations
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.session import SessionLocal
from app.jobs.tasks import poll_waiting_orders
from app.models import Order, Provider, Price, User
from decimal import Decimal

from app.providers.router import final_price


def create_order(client, user_token):
    response = client.post(
        "/api/v1/orders",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"service_code": "telegram", "country_iso2": "ID"},
    )
    assert response.status_code == 200, response.text
    return response.json()


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
    poll_waiting_orders()
    balance = client.get("/api/v1/balance", headers={"Authorization": f"Bearer {user_token}"}).json()
    assert balance["balance"] == "25.0000"
    assert balance["held_balance"] == "0.0000"


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
