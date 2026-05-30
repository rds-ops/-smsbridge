from __future__ import annotations

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import ApiRequestLog, Order, SupplierActivation


def create_supplier(client, admin_token) -> dict:
    response = client.post(
        "/admin/suppliers",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": "Log Supplier", "email": "logs@example.com", "status": "active", "reward_percent": "70.00"},
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


def update_inventory(client, api_key: str):
    response = client.post(
        "/supplier/v1/inventory/update",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "items": [
                {
                    "service_code": "telegram",
                    "country_iso2": "ID",
                    "operator": "any",
                    "available_count": 5,
                    "success_rate": "95.00",
                    "avg_sms_time_seconds": 30,
                    "status": "active",
                }
            ]
        },
    )
    assert response.status_code == 200, response.text


def latest_log(endpoint: str, status_code: int | None = None) -> ApiRequestLog:
    db = SessionLocal()
    try:
        stmt = select(ApiRequestLog).where(ApiRequestLog.endpoint == endpoint)
        if status_code is not None:
            stmt = stmt.where(ApiRequestLog.status_code == status_code)
        log = db.scalar(stmt.order_by(ApiRequestLog.created_at.desc(), ApiRequestLog.id.desc()))
        assert log is not None
        return log
    finally:
        db.close()


def test_supplier_me_request_logs_supplier_id_and_admin_can_view_it(client, admin_token):
    supplier = create_supplier(client, admin_token)
    api_key = supplier_key(client, admin_token, supplier["id"])

    response = client.get("/supplier/v1/me", headers={"Authorization": f"Bearer {api_key}"})

    assert response.status_code == 200, response.text
    log = latest_log("/supplier/v1/me", 200)
    assert log.supplier_id == supplier["id"]
    assert log.user_id is None

    admin_logs = client.get("/admin/api-request-logs", headers={"Authorization": f"Bearer {admin_token}"})
    assert admin_logs.status_code == 200, admin_logs.text
    supplier_log = next(item for item in admin_logs.json() if item["id"] == log.id)
    assert supplier_log["supplier_id"] == supplier["id"]


def test_supplier_sms_request_is_logged_without_body_or_sms_text(client, admin_token, user_token):
    supplier = create_supplier(client, admin_token)
    api_key = supplier_key(client, admin_token, supplier["id"])
    update_inventory(client, api_key)
    order = client.post(
        "/api/v1/orders",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"service_code": "telegram", "country_iso2": "ID"},
    ).json()
    db = SessionLocal()
    try:
        order_entity = db.scalar(select(Order).where(Order.public_id == order["public_id"]))
        activation = db.scalar(select(SupplierActivation).where(SupplierActivation.order_id == order_entity.id))
        supplier_activation_id = activation.supplier_activation_id
    finally:
        db.close()

    sms_text = "Telegram code: 123456"
    response = client.post(
        "/supplier/v1/sms",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "supplier_sms_id": "log-sms-1",
            "supplier_activation_id": supplier_activation_id,
            "phone_number": order["phone_number"],
            "phone_from": "Telegram",
            "text": sms_text,
        },
    )

    assert response.status_code == 200, response.text
    log = latest_log("/supplier/v1/sms", 200)
    assert log.supplier_id == supplier["id"]
    assert log.endpoint == "/supplier/v1/sms"
    assert log.method == "POST"
    assert sms_text not in log.endpoint
    assert sms_text not in log.method
    assert sms_text not in (log.ip_address or "")


def test_failed_supplier_auth_request_is_logged_without_supplier_id(client):
    response = client.get("/supplier/v1/me", headers={"Authorization": "Bearer bad-supplier-key"})

    assert response.status_code == 401
    log = latest_log("/supplier/v1/me", 401)
    assert log.supplier_id is None
    assert log.user_id is None


def test_existing_buyer_request_logging_still_sets_user_id(client, user_token):
    response = client.get("/api/v1/balance", headers={"Authorization": f"Bearer {user_token}"})

    assert response.status_code == 200
    log = latest_log("/api/v1/balance", 200)
    assert log.user_id == 2
    assert log.supplier_id is None
