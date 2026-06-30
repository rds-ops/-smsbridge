from __future__ import annotations
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import object_session

from app.db.session import SessionLocal
from app.jobs.tasks import poll_waiting_orders
from app.models import (
    AuditLog,
    Order,
    OrderEvent,
    Provider,
    SmsMessage,
    Supplier,
    SupplierActivation,
    SupplierApplication,
    SupplierInventory,
    SupplierReleaseRetry,
    SupplierSms,
    SupplierTransaction,
    User,
    WalletTransaction,
)
from app.services import orders as order_service
from app.services import suppliers as supplier_service
from app.services.supplier_release_retries import process_due_release_retries
from app.services.supplier_reservations import (
    SupplierReservationAmbiguousResponse,
    SupplierReservationResult,
    SupplierReservationUnavailable,
)


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


def supplier_application_payload(**overrides):
    payload = {
        "contact_name": "Acme Numbers",
        "email": "supplier-app@example.com",
        "contact_handle": "@acme_numbers",
        "country_market": "Indonesia",
        "number_type": "real_sim",
        "estimated_daily_volume": 100,
        "estimated_monthly_volume": 3000,
        "integration_availability": "yes",
        "inventory_description": "We operate compliant OTP testing inventory for QA and onboarding flows.",
        "api_url": "https://supplier.example.com/v1/reservations",
        "equipment_details": "SIM bank and internal routing platform.",
        "website": "https://supplier.example.com",
    }
    payload.update(overrides)
    return payload


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


def test_reservation_enabled_requires_safe_config(client, admin_token):
    missing_url = client.post(
        "/admin/suppliers",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "name": "Missing URL Supplier",
            "status": "active",
            "reservation_enabled": True,
        },
    )
    assert missing_url.status_code == 400
    assert "reservation_url" in missing_url.json()["detail"]

    bad_auth = client.post(
        "/admin/suppliers",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "name": "Bad Auth Supplier",
            "status": "active",
            "reservation_enabled": True,
            "reservation_url": "https://supplier.example.test/v1/reservations",
            "reservation_auth_type": "bearer",
        },
    )
    assert bad_auth.status_code == 400
    assert "secret" in bad_auth.json()["detail"]

    supplier = create_supplier(client, admin_token)
    patch_missing_url = client.patch(
        f"/admin/suppliers/{supplier['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reservation_enabled": True},
    )
    assert patch_missing_url.status_code == 400


def test_supplier_reservation_secret_is_redacted_from_audit_logs(client, admin_token):
    response = client.post(
        "/admin/suppliers",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "name": "Audit Reservation Supplier",
            "status": "active",
            "reservation_enabled": True,
            "reservation_url": "https://supplier.example.test/v1/reservations",
            "reservation_auth_type": "bearer",
            "reservation_auth_secret_encrypted": "enc:super-secret",
        },
    )

    assert response.status_code == 200, response.text
    db = SessionLocal()
    try:
        audit = db.scalar(
            select(AuditLog).where(
                AuditLog.action == "supplier.create",
                AuditLog.entity_id == str(response.json()["id"]),
            )
        )
        assert audit is not None
        assert audit.log_metadata["reservation_auth_secret_encrypted"] == "[redacted]"
        assert "super-secret" not in str(audit.log_metadata)
    finally:
        db.close()


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
    assert "api_key" not in supplier
    assert "api_key_hash" not in supplier
    api_key = supplier_key(client, admin_token, supplier["id"])
    assert api_key.startswith("sbsup_live_")
    detail = client.get(f"/admin/suppliers/{supplier['id']}", headers={"Authorization": f"Bearer {admin_token}"})
    assert detail.status_code == 200
    assert "api_key" not in detail.json()
    assert "api_key_hash" not in detail.json()
    response = client.get("/supplier/v1/me", headers={"Authorization": f"Bearer {api_key}"})
    assert response.status_code == 200, response.text
    assert response.json()["id"] == supplier["id"]
    assert "reservation_auth_secret_encrypted" not in response.json()
    assert "reservation_url" not in response.json()
    db = SessionLocal()
    try:
        supplier_entity = db.get(Supplier, supplier["id"])
        assert supplier_entity.api_key_hash is not None
        assert supplier_entity.api_key_hash != api_key
    finally:
        db.close()


def test_public_supplier_application_is_persisted_safely(client):
    response = client.post("/supplier/v1/applications", json=supplier_application_payload())

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "received"
    assert body["public_id"]
    assert "api_key" not in body
    assert "inventory_description" not in body

    db = SessionLocal()
    try:
        application = db.scalar(select(SupplierApplication).where(SupplierApplication.public_id == body["public_id"]))
        assert application is not None
        assert application.status == "pending"
        assert application.email == "supplier-app@example.com"
        assert application.contact_name == "Acme Numbers"
        assert application.api_url == "https://supplier.example.com/v1/reservations"
    finally:
        db.close()


def test_supplier_application_rejects_invalid_public_input(client):
    response = client.post(
        "/supplier/v1/applications",
        json=supplier_application_payload(api_url="ftp://supplier.example.com/reservations"),
    )

    assert response.status_code == 400
    assert "api_url" in response.json()["detail"]


def test_admin_can_list_detail_and_review_supplier_applications(client, admin_token):
    created = client.post("/supplier/v1/applications", json=supplier_application_payload(email="review@example.com"))
    assert created.status_code == 200, created.text

    listed = client.get("/admin/supplier-applications", headers={"Authorization": f"Bearer {admin_token}"})
    assert listed.status_code == 200, listed.text
    row = next(item for item in listed.json() if item["public_id"] == created.json()["public_id"])
    assert row["status"] == "pending"
    assert row["email"] == "review@example.com"
    assert row["inventory_description"]
    assert "api_key" not in row

    detail = client.get(f"/admin/supplier-applications/{row['id']}", headers={"Authorization": f"Bearer {admin_token}"})
    assert detail.status_code == 200, detail.text
    assert detail.json()["public_id"] == created.json()["public_id"]

    reviewed = client.patch(
        f"/admin/supplier-applications/{row['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "needs_info", "internal_review_note": "Ask for sandbox callback URL."},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "needs_info"
    assert reviewed.json()["internal_review_note"] == "Ask for sandbox callback URL."
    assert reviewed.json()["reviewed_by_user_id"] is not None
    assert reviewed.json()["reviewed_at"] is not None


def test_supplier_application_approval_does_not_create_supplier_or_key(client, admin_token):
    created = client.post("/supplier/v1/applications", json=supplier_application_payload(email="approve@example.com"))
    assert created.status_code == 200, created.text
    before_suppliers = client.get("/admin/suppliers", headers={"Authorization": f"Bearer {admin_token}"}).json()
    listed = client.get("/admin/supplier-applications", headers={"Authorization": f"Bearer {admin_token}"})
    application = next(item for item in listed.json() if item["public_id"] == created.json()["public_id"])

    approved = client.patch(
        f"/admin/supplier-applications/{application['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "approved"},
    )

    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    after_suppliers = client.get("/admin/suppliers", headers={"Authorization": f"Bearer {admin_token}"}).json()
    assert len(after_suppliers) == len(before_suppliers)
    assert "api_key" not in approved.json()


def test_non_admin_cannot_access_supplier_applications(client, user_token):
    created = client.post("/supplier/v1/applications", json=supplier_application_payload(email="blocked-review@example.com"))
    assert created.status_code == 200, created.text

    listed = client.get("/admin/supplier-applications", headers={"Authorization": f"Bearer {user_token}"})
    assert listed.status_code == 403


def test_blocked_supplier_cannot_update_inventory(client, admin_token):
    supplier = create_supplier(client, admin_token, status="blocked")
    api_key = supplier_key(client, admin_token, supplier["id"])
    response = update_inventory(client, api_key)
    assert response.status_code == 403


def test_blocked_supplier_inventory_is_excluded_from_routing(client, admin_token):
    supplier = create_supplier(client, admin_token, status="blocked")
    db = SessionLocal()
    try:
        db.add(
            SupplierInventory(
                supplier_id=supplier["id"],
                service_code="telegram",
                country_iso2="ID",
                operator=None,
                available_count=10,
                status="active",
            )
        )
        db.commit()

        selected = supplier_service.select_inventory(db, "telegram", "ID", None)

        assert selected is None
    finally:
        db.close()


def test_supplier_can_update_inventory(client, admin_token):
    supplier = create_supplier(client, admin_token)
    api_key = supplier_key(client, admin_token, supplier["id"])
    response = update_inventory(client, api_key, count=25)
    assert response.status_code == 200, response.text
    assert response.json()["updated"] == 1
    inventory = client.get(f"/admin/suppliers/{supplier['id']}/inventory", headers={"Authorization": f"Bearer {admin_token}"})
    assert inventory.status_code == 200
    assert inventory.json()[0]["available_count"] == 25


def test_supplier_can_list_own_activations_with_sms_summary(client, admin_token, user_token):
    supplier = create_supplier(client, admin_token)
    api_key = supplier_key(client, admin_token, supplier["id"])
    assert update_inventory(client, api_key, count=5).status_code == 200
    order = buy_order(client, user_token)
    db = SessionLocal()
    try:
        activation = db.scalar(select(SupplierActivation).join(Order, SupplierActivation.order_id == Order.id).where(Order.public_id == order["public_id"]))
        supplier_activation_id = activation.supplier_activation_id
    finally:
        db.close()

    sms = client.post(
        "/supplier/v1/sms",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "supplier_sms_id": "activation-list-sms",
            "phone_number": order["phone_number"],
            "phone_from": "Telegram",
            "text": "Telegram code: 112233",
            "supplier_activation_id": supplier_activation_id,
        },
    )
    assert sms.status_code == 200, sms.text

    response = client.get("/supplier/v1/activations", headers={"Authorization": f"Bearer {api_key}"})

    assert response.status_code == 200, response.text
    rows = response.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["supplier_activation_id"] == supplier_activation_id
    assert row["phone_number"] == order["phone_number"]
    assert row["service_code"] == "telegram"
    assert row["country_iso2"] == "ID"
    assert row["status"] == "sms_received"
    assert row["order_public_id"] == order["public_id"]
    assert row["sms_count"] == 1
    assert row["latest_sms_at"] is not None
    assert "client_price" not in row
    assert "supplier_reward" not in row
    assert "sms_text" not in row
    assert "sms_code" not in row
    assert "provider_cost" not in row


def test_supplier_activation_list_is_supplier_scoped(client, admin_token, user_token):
    first_supplier = create_supplier(client, admin_token)
    first_key = supplier_key(client, admin_token, first_supplier["id"])
    assert update_inventory(client, first_key, count=5).status_code == 200
    order = buy_order(client, user_token)

    second_supplier = create_supplier(client, admin_token)
    second_key = supplier_key(client, admin_token, second_supplier["id"])

    first_response = client.get("/supplier/v1/activations", headers={"Authorization": f"Bearer {first_key}"})
    second_response = client.get("/supplier/v1/activations", headers={"Authorization": f"Bearer {second_key}"})

    assert first_response.status_code == 200, first_response.text
    assert [row["order_public_id"] for row in first_response.json()] == [order["public_id"]]
    assert second_response.status_code == 200, second_response.text
    assert second_response.json() == []


def test_supplier_activation_list_pagination_and_status_filter(client, admin_token):
    supplier = create_supplier(client, admin_token)
    api_key = supplier_key(client, admin_token, supplier["id"])
    db = SessionLocal()
    try:
        for index, status in enumerate(["waiting_sms", "sms_received", "cancelled", "expired"]):
            db.add(
                SupplierActivation(
                    supplier_id=supplier["id"],
                    supplier_activation_id=f"manual-act-{index}",
                    phone_number=f"+62810000000{index}",
                    service_code="telegram",
                    country_iso2="ID",
                    operator=None,
                    status=status,
                    client_price=Decimal("0.5000"),
                    supplier_reward=Decimal("0.3500"),
                )
            )
        db.commit()
    finally:
        db.close()

    page = client.get("/supplier/v1/activations?limit=2&offset=1", headers={"Authorization": f"Bearer {api_key}"})
    filtered = client.get("/supplier/v1/activations?status=cancelled", headers={"Authorization": f"Bearer {api_key}"})

    assert page.status_code == 200, page.text
    assert len(page.json()) == 2
    assert filtered.status_code == 200, filtered.text
    assert len(filtered.json()) == 1
    assert filtered.json()[0]["status"] == "cancelled"
    assert filtered.json()[0]["supplier_activation_id"] == "manual-act-2"


def test_supplier_activation_list_requires_auth(client):
    response = client.get("/supplier/v1/activations")

    assert response.status_code in {401, 403}


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
        session = object_session(supplier_entity)
        order_entity = session.scalar(select(Order).where(Order.public_id == request.order_public_id))
        hold = session.scalar(
            select(WalletTransaction).where(
                WalletTransaction.order_id == order_entity.id,
                WalletTransaction.type == "hold",
                WalletTransaction.status == "completed",
            )
        )
        seen["hold_before_callback"] = hold is not None
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
    assert seen["hold_before_callback"] is True

    db = SessionLocal()
    try:
        order_entity = db.scalar(select(Order).where(Order.public_id == order["public_id"]))
        assert order_entity.provider_order_id == "real-act-123"
        activation = db.scalar(select(SupplierActivation).where(SupplierActivation.order_id == order_entity.id))
        assert activation.supplier_activation_id == "real-act-123"
        assert activation.phone_number == "+628111111111"
        inventory = db.scalar(select(SupplierInventory).where(SupplierInventory.supplier_id == supplier["id"]))
        assert inventory.last_reservation_at is not None
        assert inventory.last_reservation_error is None
    finally:
        db.close()


def test_reservation_enabled_supplier_works_in_production_like_env(client, admin_token, user_token, monkeypatch):
    monkeypatch.setattr("app.services.suppliers.settings.environment", "production")
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
            supplier_activation_id="prod-real-act",
            phone_number="+628999999999",
        ),
    )

    order = buy_order(client, user_token)

    assert order["status"] == "waiting_sms"
    assert order["phone_number"] == "+628999999999"


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


def test_supplier_sms_without_activation_id_transitions_order_by_phone(client, admin_token, user_token, monkeypatch):
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
            supplier_activation_id="real-act-phone-only",
            phone_number="+628222333444",
        ),
    )

    order = buy_order(client, user_token)
    payload = {
        "supplier_sms_id": "real-sms-phone-only",
        "phone_number": "+628222333444",
        "phone_from": "Telegram",
        "text": "Your Telegram code is 12345",
    }
    first = client.post("/supplier/v1/sms", headers={"Authorization": f"Bearer {api_key}"}, json=payload)
    second = client.post("/supplier/v1/sms", headers={"Authorization": f"Bearer {api_key}"}, json=payload)

    assert first.status_code == 200, first.text
    assert first.json() == {"status": "SUCCESS", "duplicate": False}
    assert second.status_code == 200, second.text
    assert second.json() == {"status": "SUCCESS", "duplicate": True}

    fetched = client.get(f"/api/v1/orders/{order['public_id']}", headers={"Authorization": f"Bearer {user_token}"})
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["status"] == "sms_received"
    assert fetched.json()["sms_code"] == "12345"
    assert fetched.json()["sms_text"] == "Your Telegram code is 12345"

    db = SessionLocal()
    try:
        order_entity = db.scalar(select(Order).where(Order.public_id == order["public_id"]))
        assert order_entity.status == "sms_received"
        activation = db.scalar(select(SupplierActivation).where(SupplierActivation.order_id == order_entity.id))
        assert activation.supplier_activation_id == "real-act-phone-only"
        assert activation.status == "sms_received"
        supplier_sms = db.scalar(select(SupplierSms).where(SupplierSms.supplier_sms_id == "real-sms-phone-only"))
        assert supplier_sms.order_id == order_entity.id
        messages = list(db.scalars(select(SmsMessage).where(SmsMessage.order_id == order_entity.id)))
        assert len(messages) == 1
        events = list(
            db.scalars(
                select(OrderEvent).where(
                    OrderEvent.order_id == order_entity.id,
                    OrderEvent.old_status == "waiting_sms",
                    OrderEvent.new_status == "sms_received",
                )
            )
        )
        assert len(events) == 1
    finally:
        db.close()


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
        assert inventory.failed_reservation_count == 1
        assert inventory.last_reservation_error == "supplier unavailable"
        assert db.scalar(select(SupplierActivation).where(SupplierActivation.supplier_id == supplier["id"])) is None
        assert db.scalar(select(Order).where(Order.user_id == 2)) is None
        assert db.scalar(select(OrderEvent)) is None
    finally:
        db.close()


def test_supplier_reservation_failure_after_hold_refunds_if_committed(client, admin_token, monkeypatch):
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
        session = object_session(supplier_entity)
        order_entity = session.scalar(select(Order).where(Order.public_id == request.order_public_id))
        assert session.scalar(
            select(WalletTransaction).where(
                WalletTransaction.order_id == order_entity.id,
                WalletTransaction.type == "hold",
                WalletTransaction.status == "completed",
            )
        )
        raise SupplierReservationUnavailable("supplier unavailable after hold")

    monkeypatch.setattr("app.services.suppliers.reserve_supplier_number", fail_reservation)

    db = SessionLocal()
    try:
        user = db.get(User, 2)
        try:
            order_service.create_order(db, user, "telegram", "ID")
        except HTTPException as exc:
            assert exc.status_code == 502
        else:
            raise AssertionError("supplier reservation failure should raise")

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
        assert db.scalar(select(SupplierActivation).where(SupplierActivation.supplier_id == supplier["id"])) is None
        inventory = db.scalar(select(SupplierInventory).where(SupplierInventory.supplier_id == supplier["id"]))
        assert inventory.available_count == 5
    finally:
        db.close()


def test_ambiguous_supplier_reservation_creates_failed_activation_and_release_retry(client, admin_token, user_token, monkeypatch):
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

    def ambiguous_reservation(supplier_entity, request, *, idempotency_key):
        raise SupplierReservationAmbiguousResponse(
            "supplier returned malformed reserved response",
            supplier_activation_id="ambiguous-act-1",
            phone_number="+628199999999",
        )

    monkeypatch.setattr("app.services.suppliers.reserve_supplier_number", ambiguous_reservation)

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
        user = db.get(User, 2)
        db.refresh(user.wallet)
        assert user.wallet.balance == Decimal("25.0000")
        assert user.wallet.held_balance == Decimal("0.0000")

        failed_order = db.scalar(select(Order).where(Order.user_id == user.id, Order.status == "failed"))
        assert failed_order is not None
        assert failed_order.provider_order_id == "ambiguous-act-1"
        assert failed_order.phone_number == "+628199999999"
        activation = db.scalar(select(SupplierActivation).where(SupplierActivation.order_id == failed_order.id))
        assert activation is not None
        assert activation.status == "failed"
        assert activation.supplier_activation_id == "ambiguous-act-1"
        assert activation.phone_number == "+628199999999"
        retry = db.scalar(select(SupplierReleaseRetry).where(SupplierReleaseRetry.supplier_activation_id == activation.id))
        assert retry is not None
        assert retry.status == "pending"
        assert retry.reason == "failed"
        assert "malformed reserved response" in retry.last_error
        assert db.scalar(select(WalletTransaction).where(WalletTransaction.order_id == failed_order.id)) is None
        inventory = db.scalar(select(SupplierInventory).where(SupplierInventory.supplier_id == supplier["id"]))
        assert inventory.available_count == 5
        assert inventory.failed_reservation_count == 1
        assert inventory.failed_release_count == 1
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


def test_production_blocks_legacy_fake_supplier_path(client, admin_token, user_token, monkeypatch):
    monkeypatch.setattr("app.services.suppliers.settings.environment", "production")
    supplier = create_supplier(client, admin_token)
    api_key = supplier_key(client, admin_token, supplier["id"])
    assert update_inventory(client, api_key, count=5).status_code == 200
    db = SessionLocal()
    try:
        mock_provider = db.scalar(select(Provider).where(Provider.code == "mock"))
        mock_provider.status = "inactive"
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
    db = SessionLocal()
    try:
        inventory = db.scalar(select(SupplierInventory).where(SupplierInventory.supplier_id == supplier["id"]))
        assert inventory.available_count == 5
        assert inventory.failed_reservation_count == 1
        assert inventory.last_reservation_error == "reservation_callback_required"
        assert db.scalar(select(SupplierActivation).where(SupplierActivation.supplier_id == supplier["id"])) is None
    finally:
        db.close()
    inventory_response = client.get(
        f"/admin/suppliers/{supplier['id']}/inventory",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert inventory_response.status_code == 200, inventory_response.text
    assert inventory_response.json()[0]["failed_reservation_count"] == 1


def test_cancel_order_triggers_release_callback_for_reservation_enabled_supplier(client, admin_token, user_token, monkeypatch):
    supplier = create_supplier(client, admin_token)
    assert client.patch(
        f"/admin/suppliers/{supplier['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reservation_enabled": True, "reservation_url": "https://supplier.example.test/v1/reservations"},
    ).status_code == 200
    api_key = supplier_key(client, admin_token, supplier["id"])
    assert update_inventory(client, api_key, count=5).status_code == 200
    monkeypatch.setattr(
        "app.services.suppliers.reserve_supplier_number",
        lambda supplier_entity, request, *, idempotency_key: SupplierReservationResult(
            supplier_activation_id="real-act-release",
            phone_number="+628333333333",
        ),
    )
    seen = {}

    def fake_release(supplier_entity, request, *, idempotency_key):
        seen["supplier_id"] = supplier_entity.id
        seen["request"] = request
        seen["idempotency_key"] = idempotency_key

    monkeypatch.setattr("app.services.suppliers.release_supplier_number", fake_release)

    order = buy_order(client, user_token)
    cancelled = client.post(f"/api/v1/orders/{order['public_id']}/cancel", headers={"Authorization": f"Bearer {user_token}"})

    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    assert seen["supplier_id"] == supplier["id"]
    assert seen["idempotency_key"] == f"sb-release-{order['public_id']}"
    assert seen["request"].order_public_id == order["public_id"]
    assert seen["request"].supplier_activation_id == "real-act-release"
    assert seen["request"].phone_number == "+628333333333"
    assert seen["request"].reason == "cancelled"
    db = SessionLocal()
    try:
        inventory = db.scalar(select(SupplierInventory).where(SupplierInventory.supplier_id == supplier["id"]))
        assert inventory.last_release_at is not None
        assert inventory.last_release_error is None
    finally:
        db.close()


def test_expired_order_triggers_release_callback_for_reservation_enabled_supplier(client, admin_token, user_token, monkeypatch):
    supplier = create_supplier(client, admin_token)
    assert client.patch(
        f"/admin/suppliers/{supplier['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reservation_enabled": True, "reservation_url": "https://supplier.example.test/v1/reservations"},
    ).status_code == 200
    api_key = supplier_key(client, admin_token, supplier["id"])
    assert update_inventory(client, api_key, count=5).status_code == 200
    monkeypatch.setattr(
        "app.services.suppliers.reserve_supplier_number",
        lambda supplier_entity, request, *, idempotency_key: SupplierReservationResult(
            supplier_activation_id="real-act-expire",
            phone_number="+628444444444",
        ),
    )
    seen = {}

    def fake_release(supplier_entity, request, *, idempotency_key):
        seen["request"] = request
        seen["idempotency_key"] = idempotency_key

    monkeypatch.setattr("app.services.suppliers.release_supplier_number", fake_release)

    order = buy_order(client, user_token)
    db = SessionLocal()
    try:
        order_entity = db.scalar(select(Order).where(Order.public_id == order["public_id"]))
        order_entity.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    finally:
        db.close()

    poll_waiting_orders()

    assert seen["idempotency_key"] == f"sb-release-{order['public_id']}"
    assert seen["request"].supplier_activation_id == "real-act-expire"
    assert seen["request"].reason == "expired"
    fetched = client.get(f"/api/v1/orders/{order['public_id']}", headers={"Authorization": f"Bearer {user_token}"})
    assert fetched.json()["status"] == "expired"


def test_release_failure_does_not_block_cancel_or_refund(client, admin_token, user_token, monkeypatch):
    supplier = create_supplier(client, admin_token)
    assert client.patch(
        f"/admin/suppliers/{supplier['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reservation_enabled": True, "reservation_url": "https://supplier.example.test/v1/reservations"},
    ).status_code == 200
    api_key = supplier_key(client, admin_token, supplier["id"])
    assert update_inventory(client, api_key, count=5).status_code == 200
    monkeypatch.setattr(
        "app.services.suppliers.reserve_supplier_number",
        lambda supplier_entity, request, *, idempotency_key: SupplierReservationResult(
            supplier_activation_id="real-act-release-fail",
            phone_number="+628555555555",
        ),
    )

    def fail_release(supplier_entity, request, *, idempotency_key):
        raise SupplierReservationUnavailable("supplier release unavailable")

    monkeypatch.setattr("app.services.suppliers.release_supplier_number", fail_release)

    order = buy_order(client, user_token)
    cancelled = client.post(f"/api/v1/orders/{order['public_id']}/cancel", headers={"Authorization": f"Bearer {user_token}"})

    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    balance = client.get("/api/v1/balance", headers={"Authorization": f"Bearer {user_token}"}).json()
    assert balance["balance"] == "25.0000"
    assert balance["held_balance"] == "0.0000"
    db = SessionLocal()
    try:
        inventory = db.scalar(select(SupplierInventory).where(SupplierInventory.supplier_id == supplier["id"]))
        assert inventory.failed_release_count == 1
        assert inventory.last_release_error == "supplier release unavailable"
        retry = db.scalar(select(SupplierReleaseRetry).where(SupplierReleaseRetry.supplier_id == supplier["id"]))
        assert retry is not None
        assert retry.status == "pending"
        assert retry.attempt_count == 0
        assert retry.last_error == "supplier release unavailable"
    finally:
        db.close()

    inventory_response = client.get(
        f"/admin/suppliers/{supplier['id']}/inventory",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert inventory_response.status_code == 200, inventory_response.text
    inventory_body = inventory_response.json()[0]
    assert inventory_body["failed_release_count"] == 1
    assert inventory_body["last_release_error"] == "supplier release unavailable"


def test_failed_release_does_not_create_duplicate_retry_jobs(client, admin_token, user_token, monkeypatch):
    supplier = create_supplier(client, admin_token)
    assert client.patch(
        f"/admin/suppliers/{supplier['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reservation_enabled": True, "reservation_url": "https://supplier.example.test/v1/reservations"},
    ).status_code == 200
    api_key = supplier_key(client, admin_token, supplier["id"])
    assert update_inventory(client, api_key, count=5).status_code == 200
    monkeypatch.setattr(
        "app.services.suppliers.reserve_supplier_number",
        lambda supplier_entity, request, *, idempotency_key: SupplierReservationResult(
            supplier_activation_id="real-act-release-duplicate",
            phone_number="+628555555556",
        ),
    )

    def fail_release(supplier_entity, request, *, idempotency_key):
        raise SupplierReservationUnavailable("supplier release unavailable")

    monkeypatch.setattr("app.services.suppliers.release_supplier_number", fail_release)

    order = buy_order(client, user_token)
    first = client.post(f"/api/v1/orders/{order['public_id']}/cancel", headers={"Authorization": f"Bearer {user_token}"})
    second = client.post(f"/api/v1/orders/{order['public_id']}/cancel", headers={"Authorization": f"Bearer {user_token}"})
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text

    db = SessionLocal()
    try:
        retries = list(db.scalars(select(SupplierReleaseRetry).where(SupplierReleaseRetry.supplier_id == supplier["id"])))
        assert len(retries) == 1
    finally:
        db.close()


def test_release_retry_worker_marks_success(client, admin_token, user_token, monkeypatch):
    supplier = create_supplier(client, admin_token)
    assert client.patch(
        f"/admin/suppliers/{supplier['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reservation_enabled": True, "reservation_url": "https://supplier.example.test/v1/reservations"},
    ).status_code == 200
    api_key = supplier_key(client, admin_token, supplier["id"])
    assert update_inventory(client, api_key, count=5).status_code == 200
    monkeypatch.setattr(
        "app.services.suppliers.reserve_supplier_number",
        lambda supplier_entity, request, *, idempotency_key: SupplierReservationResult(
            supplier_activation_id="real-act-release-retry-success",
            phone_number="+628555555557",
        ),
    )

    def fail_initial_release(supplier_entity, request, *, idempotency_key):
        raise SupplierReservationUnavailable("supplier release unavailable")

    monkeypatch.setattr("app.services.suppliers.release_supplier_number", fail_initial_release)
    order = buy_order(client, user_token)
    cancelled = client.post(f"/api/v1/orders/{order['public_id']}/cancel", headers={"Authorization": f"Bearer {user_token}"})
    assert cancelled.status_code == 200, cancelled.text

    seen = {}

    def succeed_retry(supplier_entity, request, *, idempotency_key):
        seen["idempotency_key"] = idempotency_key
        seen["request"] = request

    monkeypatch.setattr("app.services.supplier_release_retries.release_supplier_number", succeed_retry)
    db = SessionLocal()
    try:
        retry = db.scalar(select(SupplierReleaseRetry).where(SupplierReleaseRetry.supplier_id == supplier["id"]))
        retry.next_retry_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()

        assert process_due_release_retries(db) == 1
        db.commit()
        db.refresh(retry)
        inventory = db.scalar(select(SupplierInventory).where(SupplierInventory.supplier_id == supplier["id"]))
        assert retry.status == "succeeded"
        assert retry.attempt_count == 1
        assert retry.last_error is None
        assert inventory.last_release_at is not None
        assert inventory.last_release_error is None
    finally:
        db.close()

    assert seen["idempotency_key"] == f"sb-release-{order['public_id']}"
    assert seen["request"].supplier_activation_id == "real-act-release-retry-success"


def test_release_retry_worker_retries_then_marks_dead(client, admin_token, user_token, monkeypatch):
    supplier = create_supplier(client, admin_token)
    assert client.patch(
        f"/admin/suppliers/{supplier['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reservation_enabled": True, "reservation_url": "https://supplier.example.test/v1/reservations"},
    ).status_code == 200
    api_key = supplier_key(client, admin_token, supplier["id"])
    assert update_inventory(client, api_key, count=5).status_code == 200
    monkeypatch.setattr(
        "app.services.suppliers.reserve_supplier_number",
        lambda supplier_entity, request, *, idempotency_key: SupplierReservationResult(
            supplier_activation_id="real-act-release-retry-dead",
            phone_number="+628555555558",
        ),
    )

    def fail_release(supplier_entity, request, *, idempotency_key):
        raise SupplierReservationUnavailable("supplier release unavailable")

    monkeypatch.setattr("app.services.suppliers.release_supplier_number", fail_release)
    monkeypatch.setattr("app.services.supplier_release_retries.release_supplier_number", fail_release)
    order = buy_order(client, user_token)
    cancelled = client.post(f"/api/v1/orders/{order['public_id']}/cancel", headers={"Authorization": f"Bearer {user_token}"})
    assert cancelled.status_code == 200, cancelled.text

    db = SessionLocal()
    try:
        retry = db.scalar(select(SupplierReleaseRetry).where(SupplierReleaseRetry.supplier_id == supplier["id"]))
        now = datetime.now(timezone.utc)
        for index in range(4):
            retry.next_retry_at = now - timedelta(seconds=1)
            db.commit()
            assert process_due_release_retries(db, now=now + timedelta(hours=index)) == 1
            db.commit()
            db.refresh(retry)

        inventory = db.scalar(select(SupplierInventory).where(SupplierInventory.supplier_id == supplier["id"]))
        assert retry.status == "dead"
        assert retry.attempt_count == 4
        assert retry.last_error == "supplier release unavailable"
        assert inventory.failed_release_count == 5
    finally:
        db.close()


def test_admin_can_view_supplier_release_retries(client, admin_token, user_token, monkeypatch):
    supplier = create_supplier(client, admin_token)
    assert client.patch(
        f"/admin/suppliers/{supplier['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reservation_enabled": True, "reservation_url": "https://supplier.example.test/v1/reservations"},
    ).status_code == 200
    api_key = supplier_key(client, admin_token, supplier["id"])
    assert update_inventory(client, api_key, count=5).status_code == 200
    monkeypatch.setattr(
        "app.services.suppliers.reserve_supplier_number",
        lambda supplier_entity, request, *, idempotency_key: SupplierReservationResult(
            supplier_activation_id="real-act-release-admin-visible",
            phone_number="+628555555559",
        ),
    )
    monkeypatch.setattr(
        "app.services.suppliers.release_supplier_number",
        lambda supplier_entity, request, *, idempotency_key: (_ for _ in ()).throw(
            SupplierReservationUnavailable("supplier release unavailable")
        ),
    )

    order = buy_order(client, user_token)
    cancelled = client.post(f"/api/v1/orders/{order['public_id']}/cancel", headers={"Authorization": f"Bearer {user_token}"})
    assert cancelled.status_code == 200, cancelled.text

    response = client.get("/admin/supplier-release-retries", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200, response.text
    assert response.json()[0]["status"] == "pending"
    assert response.json()[0]["reason"] == "cancelled"


def test_release_not_called_for_legacy_fake_supplier(client, admin_token, user_token, monkeypatch):
    supplier = create_supplier(client, admin_token)
    api_key = supplier_key(client, admin_token, supplier["id"])
    assert update_inventory(client, api_key, count=5).status_code == 200

    def unexpected_release(supplier_entity, request, *, idempotency_key):
        raise AssertionError("release should not be called for legacy fake supplier")

    monkeypatch.setattr("app.services.suppliers.release_supplier_number", unexpected_release)

    order = buy_order(client, user_token)
    cancelled = client.post(f"/api/v1/orders/{order['public_id']}/cancel", headers={"Authorization": f"Bearer {user_token}"})

    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"


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
