from __future__ import annotations
from decimal import Decimal

from sqlalchemy import select

from app.db.session import SessionLocal
from app.jobs.tasks import poll_waiting_orders
from app.models import Order, Provider, SmsMessage, Supplier, SupplierActivation, SupplierInventory, SupplierSms, SupplierTransaction
from app.services.supplier_reservations import SupplierReservationResult, SupplierReservationUnavailable


def create_supplier(client, admin_token, status: str = "active") -> dict:
    response = client.post(
        "/admin/suppliers",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": "Test Supplier", "email": "supplier@example.com", "status": status, "reward_percent": "70.00"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def supplier_key(client, admin_token, supplier_id: int) -> str:
    response = client.post(
        f"/admin/suppliers/{supplier_id}/api-key/regenerate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    return response.json()["api_key"]


def update_inventory(client, api_key: str, count: int = 10):
    return client.post(
        "/supplier/v1/inventory/update",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "items": [
                {
                    "service_code": "telegram",
                    "country_iso2": "ID",
                    "operator": "any",
                    "available_count": count,
                    "success_rate": "95.00",
                    "avg_sms_time_seconds": 30,
                    "status": "active",
                }
            ]
        },
    )


def buy_order(client, user_token):
    response = client.post(
        "/api/v1/orders",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"service_code": "telegram", "country_iso2": "ID"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_admin_can_create_activate_block_supplier(client, admin_token):
    supplier = create_supplier(client, admin_token, status="pending")
    assert supplier["status"] == "pending"
    assert supplier["reservation_enabled"] is False
    assert "reservation_auth_secret_encrypted" not in supplier
    activated = client.patch(
        f"/admin/suppliers/{supplier['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "active", "reward_percent": "65.00"},
    )
    assert activated.status_code == 200, activated.text
    assert activated.json()["status"] == "active"
    assert activated.json()["reward_percent"] == "65.0000"
    blocked = client.patch(
        f"/admin/suppliers/{supplier['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "blocked"},
    )
    assert blocked.status_code == 200
    assert blocked.json()["status"] == "blocked"


def test_admin_can_configure_supplier_reservation_settings(client, admin_token):
    created = client.post(
        "/admin/suppliers",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "name": "Reservation Supplier",
            "email": "reservation@example.com",
            "status": "active",
            "reward_percent": "70.00",
            "reservation_url": "https://supplier.example.test/v1/reservations",
            "reservation_auth_type": "bearer",
            "reservation_auth_secret_encrypted": "enc:test-secret",
            "reservation_timeout_seconds": 5,
            "reservation_enabled": True,
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["reservation_url"] == "https://supplier.example.test/v1/reservations"
    assert body["reservation_auth_type"] == "bearer"
    assert body["reservation_timeout_seconds"] == 5
    assert body["reservation_enabled"] is True
    assert "reservation_auth_secret_encrypted" not in body

    patched = client.patch(
        f"/admin/suppliers/{body['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reservation_enabled": False, "reservation_timeout_seconds": 10},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["reservation_enabled"] is False
    assert patched.json()["reservation_timeout_seconds"] == 10
    assert "reservation_auth_secret_encrypted" not in patched.json()

    listed = client.get("/admin/suppliers", headers={"Authorization": f"Bearer {admin_token}"})
    assert listed.status_code == 200, listed.text
    listed_supplier = next(item for item in listed.json() if item["id"] == body["id"])
    assert listed_supplier["reservation_enabled"] is False
    assert "reservation_auth_secret_encrypted" not in listed_supplier


def test_supplier_reservation_timeout_must_be_positive(client, admin_token):
    response = client.post(
        "/admin/suppliers",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "name": "Bad Timeout Supplier",
            "status": "active",
            "reservation_timeout_seconds": 0,
        },
    )
    assert response.status_code == 422


def test_admin_can_regenerate_supplier_api_key_and_auth_works(client, admin_token):
    supplier = create_supplier(client, admin_token)
    api_key = supplier_key(client, admin_token, supplier["id"])
    assert api_key.startswith("sbsup_live_")
    response = client.get("/supplier/v1/me", headers={"Authorization": f"Bearer {api_key}"})
    assert response.status_code == 200, response.text
    assert response.json()["id"] == supplier["id"]
    assert "reservation_auth_secret_encrypted" not in response.json()
    assert "reservation_url" not in response.json()


def test_blocked_supplier_cannot_update_inventory(client, admin_token):
    supplier = create_supplier(client, admin_token, status="blocked")
    api_key = supplier_key(client, admin_token, supplier["id"])
    response = update_inventory(client, api_key)
    assert response.status_code == 403


def test_supplier_can_update_inventory(client, admin_token):
    supplier = create_supplier(client, admin_token)
    api_key = supplier_key(client, admin_token, supplier["id"])
    response = update_inventory(client, api_key, count=25)
    assert response.status_code == 200, response.text
    assert response.json()["updated"] == 1
    inventory = client.get(f"/admin/suppliers/{supplier['id']}/inventory", headers={"Authorization": f"Bearer {admin_token}"})
    assert inventory.status_code == 200
    assert inventory.json()[0]["available_count"] == 25


def test_supplier_can_push_sms_and_duplicate_is_idempotent(client, admin_token, user_token):
    supplier = create_supplier(client, admin_token)
    api_key = supplier_key(client, admin_token, supplier["id"])
    assert update_inventory(client, api_key, count=5).status_code == 200
    order = buy_order(client, user_token)
    payload = {
        "supplier_sms_id": "sms_123",
        "phone_number": order["phone_number"],
        "phone_from": "Telegram",
        "text": "Telegram code: 123456",
        "supplier_activation_id": None,
    }
    db = SessionLocal()
    try:
        activation = db.scalar(select(SupplierActivation).where(SupplierActivation.order_id == db.scalar(select(Order.id).where(Order.public_id == order["public_id"]))))
        payload["supplier_activation_id"] = activation.supplier_activation_id
    finally:
        db.close()
    first = client.post("/supplier/v1/sms", headers={"Authorization": f"Bearer {api_key}"}, json=payload)
    second = client.post("/supplier/v1/sms", headers={"Authorization": f"Bearer {api_key}"}, json=payload)
    assert first.status_code == 200, first.text
    assert first.json() == {"status": "SUCCESS", "duplicate": False}
    assert second.status_code == 200, second.text
    assert second.json()["duplicate"] is True
    fetched = client.get(f"/api/v1/orders/{order['public_id']}", headers={"Authorization": f"Bearer {user_token}"})
    assert fetched.json()["status"] == "sms_received"
    assert fetched.json()["sms_code"] == "123456"
    db = SessionLocal()
    try:
        supplier_sms = db.scalar(select(SupplierSms).where(SupplierSms.supplier_sms_id == "sms_123"))
        assert supplier_sms is not None
        messages = list(db.scalars(select(SmsMessage).where(SmsMessage.order_id == supplier_sms.order_id)))
        assert len(messages) == 1
        assert messages[0].supplier_id == supplier["id"]
        assert messages[0].supplier_activation_id == supplier_sms.activation_id
        assert messages[0].source == "supplier"
        assert messages[0].external_message_id == "sms_123"
        assert messages[0].text == "Telegram code: 123456"
        assert messages[0].parsed_code == "123456"
    finally:
        db.close()


def test_reservation_enabled_supplier_uses_callback_phone_and_activation(client, admin_token, user_token, monkeypatch):
    supplier = create_supplier(client, admin_token)
    patched = client.patch(
        f"/admin/suppliers/{supplier['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reservation_enabled": True, "reservation_url": "https://supplier.example.test/reserve"},
    )
    assert patched.status_code == 200, patched.text
    api_key = supplier_key(client, admin_token, supplier["id"])
    assert update_inventory(client, api_key, count=5).status_code == 200

    seen = {}

    def fake_reserve(supplier_entity, request, *, idempotency_key):
        seen["supplier_id"] = supplier_entity.id
        seen["request"] = request
        seen["idempotency_key"] = idempotency_key
        return SupplierReservationResult(supplier_activation_id="real-act-123", phone_number="+628111111111")

    monkeypatch.setattr("app.services.suppliers.reserve_supplier_number", fake_reserve)

    order = buy_order(client, user_token)

    assert order["phone_number"] == "+628111111111"
    assert seen["supplier_id"] == supplier["id"]
    assert seen["request"].service_code == "telegram"
    assert seen["request"].country_iso2 == "ID"
    assert seen["request"].client_price
    assert seen["request"].supplier_reward
    assert seen["idempotency_key"] == f"sb-order-{order['public_id']}"

    db = SessionLocal()
    try:
        order_entity = db.scalar(select(Order).where(Order.public_id == order["public_id"]))
        assert order_entity.provider_order_id == "real-act-123"
        activation = db.scalar(select(SupplierActivation).where(SupplierActivation.order_id == order_entity.id))
        assert activation.supplier_activation_id == "real-act-123"
        assert activation.phone_number == "+628111111111"
    finally:
        db.close()


def test_supplier_sms_links_by_returned_reservation_activation_id(client, admin_token, user_token, monkeypatch):
    supplier = create_supplier(client, admin_token)
    assert client.patch(
        f"/admin/suppliers/{supplier['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reservation_enabled": True, "reservation_url": "https://supplier.example.test/reserve"},
    ).status_code == 200
    api_key = supplier_key(client, admin_token, supplier["id"])
    assert update_inventory(client, api_key, count=5).status_code == 200

    monkeypatch.setattr(
        "app.services.suppliers.reserve_supplier_number",
        lambda supplier_entity, request, *, idempotency_key: SupplierReservationResult(
            supplier_activation_id="real-act-sms",
            phone_number="+628222222222",
        ),
    )

    order = buy_order(client, user_token)
    response = client.post(
        "/supplier/v1/sms",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "supplier_sms_id": "real-sms-1",
            "phone_number": "+628222222222",
            "phone_from": "Telegram",
            "text": "Telegram code: 777888",
            "supplier_activation_id": "real-act-sms",
        },
    )

    assert response.status_code == 200, response.text
    fetched = client.get(f"/api/v1/orders/{order['public_id']}", headers={"Authorization": f"Bearer {user_token}"})
    assert fetched.json()["status"] == "sms_received"
    assert fetched.json()["sms_code"] == "777888"


def test_reservation_failure_does_not_create_fake_activation_or_hold(client, admin_token, user_token, monkeypatch):
    supplier = create_supplier(client, admin_token)
    assert client.patch(
        f"/admin/suppliers/{supplier['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reservation_enabled": True, "reservation_url": "https://supplier.example.test/reserve"},
    ).status_code == 200
    api_key = supplier_key(client, admin_token, supplier["id"])
    assert update_inventory(client, api_key, count=5).status_code == 200
    db = SessionLocal()
    try:
        mock_provider = db.scalar(select(Provider).where(Provider.code == "mock"))
        mock_provider.status = "inactive"
        db.commit()
    finally:
        db.close()

    def fail_reservation(supplier_entity, request, *, idempotency_key):
        raise SupplierReservationUnavailable("supplier unavailable")

    monkeypatch.setattr("app.services.suppliers.reserve_supplier_number", fail_reservation)

    response = client.post(
        "/api/v1/orders",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"service_code": "telegram", "country_iso2": "ID"},
    )

    assert response.status_code == 502
    balance = client.get("/api/v1/balance", headers={"Authorization": f"Bearer {user_token}"}).json()
    assert balance["balance"] == "25.0000"
    assert balance["held_balance"] == "0.0000"

    db = SessionLocal()
    try:
        inventory = db.scalar(select(SupplierInventory).where(SupplierInventory.supplier_id == supplier["id"]))
        assert inventory.available_count == 5
        assert db.scalar(select(SupplierActivation).where(SupplierActivation.supplier_id == supplier["id"])) is None
        assert db.scalar(select(Order).where(Order.user_id == 2)) is None
    finally:
        db.close()


def test_reservation_disabled_supplier_keeps_legacy_fake_path(client, admin_token, user_token):
    supplier = create_supplier(client, admin_token)
    api_key = supplier_key(client, admin_token, supplier["id"])
    assert update_inventory(client, api_key, count=5).status_code == 200

    order = buy_order(client, user_token)

    assert order["status"] == "waiting_sms"
    assert order["phone_number"].startswith("+62")
    db = SessionLocal()
    try:
        order_entity = db.scalar(select(Order).where(Order.public_id == order["public_id"]))
        assert order_entity.provider_order_id.startswith("sup_act_")
    finally:
        db.close()


def test_supplier_reward_created_only_after_completion_and_not_twice(client, admin_token, user_token):
    supplier = create_supplier(client, admin_token)
    api_key = supplier_key(client, admin_token, supplier["id"])
    assert update_inventory(client, api_key, count=5).status_code == 200
    order = buy_order(client, user_token)
    sms = client.post(
        "/supplier/v1/sms",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "supplier_sms_id": "sms_reward",
            "phone_number": order["phone_number"],
            "phone_from": "Telegram",
            "text": "Telegram code: 654321",
            "supplier_activation_id": order["provider_order_id"] if "provider_order_id" in order else None,
        },
    )
    if sms.status_code != 200:
        db = SessionLocal()
        try:
            activation = db.scalar(select(SupplierActivation).join(Order, SupplierActivation.order_id == Order.id).where(Order.public_id == order["public_id"]))
        finally:
            db.close()
        sms = client.post(
            "/supplier/v1/sms",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "supplier_sms_id": "sms_reward",
                "phone_number": order["phone_number"],
                "phone_from": "Telegram",
                "text": "Telegram code: 654321",
                "supplier_activation_id": activation.supplier_activation_id,
            },
        )
    assert sms.status_code == 200, sms.text
    first_finish = client.post(f"/api/v1/orders/{order['public_id']}/finish", headers={"Authorization": f"Bearer {user_token}"})
    second_finish = client.post(f"/api/v1/orders/{order['public_id']}/finish", headers={"Authorization": f"Bearer {user_token}"})
    assert first_finish.status_code == 200, first_finish.text
    assert second_finish.status_code == 200, second_finish.text
    db = SessionLocal()
    try:
        txs = list(db.scalars(select(SupplierTransaction).where(SupplierTransaction.type == "reward")))
        assert len(txs) == 1
        expected = (Decimal(str(first_finish.json()["price"])) * Decimal("0.7000")).quantize(Decimal("0.0001"))
        assert txs[0].amount == expected
        supplier_entity = db.get(Supplier, supplier["id"])
        assert supplier_entity.balance == txs[0].amount
    finally:
        db.close()


def test_supplier_reward_not_created_after_cancelled_order(client, admin_token, user_token):
    supplier = create_supplier(client, admin_token)
    api_key = supplier_key(client, admin_token, supplier["id"])
    assert update_inventory(client, api_key, count=5).status_code == 200
    order = buy_order(client, user_token)
    cancelled = client.post(f"/api/v1/orders/{order['public_id']}/cancel", headers={"Authorization": f"Bearer {user_token}"})
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    db = SessionLocal()
    try:
        assert db.scalar(select(SupplierTransaction).where(SupplierTransaction.type == "reward")) is None
        activation = db.scalar(select(SupplierActivation).join(Order, SupplierActivation.order_id == Order.id).where(Order.public_id == order["public_id"]))
        assert activation.status == "cancelled"
    finally:
        db.close()


def test_wholesale_tier_limits_allow_higher_active_orders(client, admin_token, user_token):
    default_orders = [buy_order(client, user_token) for _ in range(3)]
    assert len(default_orders) == 3
    blocked = client.post(
        "/api/v1/orders",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"service_code": "telegram", "country_iso2": "ID"},
    )
    assert blocked.status_code == 429

    upgraded = client.patch(
        "/admin/users/2/limits",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"tier": "wholesale"},
    )
    assert upgraded.status_code == 200, upgraded.text
    assert upgraded.json()["limit"]["max_active_orders"] == 500
    allowed = client.post(
        "/api/v1/orders",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"service_code": "telegram", "country_iso2": "ID"},
    )
    assert allowed.status_code == 200, allowed.text


def test_existing_mock_provider_flow_still_works(client, user_token):
    order = buy_order(client, user_token)
    processed = poll_waiting_orders()
    assert processed >= 1
    fetched = client.get(f"/api/v1/orders/{order['public_id']}", headers={"Authorization": f"Bearer {user_token}"})
    assert fetched.json()["status"] == "sms_received"
