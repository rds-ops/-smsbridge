from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from app.dev.fake_supplier_server import app
from app.models import Supplier
from app.services.supplier_reservations import SupplierReservationRequest, reserve_supplier_number


class FakeSupplierClient:
    def __init__(self):
        self.client = TestClient(app)

    def post(self, url, *, json, headers, timeout):
        _ = timeout
        return self.client.post(url, json=json, headers=headers)


def reservation_payload(country_iso2: str = "ID") -> dict:
    return {
        "request_id": "sb-order-1",
        "order_public_id": "order-1",
        "service_code": "telegram",
        "country_iso2": country_iso2,
        "operator": None,
        "client_price": "0.5000",
        "supplier_reward": "0.3500",
        "timeout_seconds": 120,
    }


def test_fake_supplier_reservation_success():
    client = TestClient(app)

    response = client.post("/v1/reservations", headers={"Idempotency-Key": "idem-1"}, json=reservation_payload())

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "reserved"
    assert body["supplier_activation_id"].startswith("fake-sup-act-")
    assert body["phone_number"].startswith("+")
    assert body["expires_at"]


def test_fake_supplier_idempotent_retry_returns_same_reservation():
    client = TestClient(app)
    payload = reservation_payload()

    first = client.post("/v1/reservations", headers={"Idempotency-Key": "idem-repeat"}, json=payload)
    second = client.post("/v1/reservations", headers={"Idempotency-Key": "idem-repeat"}, json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()


def test_fake_supplier_same_key_different_body_returns_conflict():
    client = TestClient(app)

    first = client.post("/v1/reservations", headers={"Idempotency-Key": "idem-conflict"}, json=reservation_payload("ID"))
    second = client.post("/v1/reservations", headers={"Idempotency-Key": "idem-conflict"}, json=reservation_payload("UZ"))

    assert first.status_code == 200
    assert second.status_code == 409


def test_fake_supplier_response_validates_against_reservation_client():
    supplier = Supplier(
        name="Fake HTTP Supplier",
        status="active",
        reservation_enabled=True,
        reservation_url="http://testserver/v1/reservations",
        reservation_auth_type="none",
        reservation_timeout_seconds=5,
    )
    request = SupplierReservationRequest(
        request_id="sb-order-client",
        order_public_id="order-client",
        service_code="telegram",
        country_iso2="ID",
        operator=None,
        client_price=Decimal("0.5000"),
        supplier_reward=Decimal("0.3500"),
        timeout_seconds=120,
    )

    result = reserve_supplier_number(supplier, request, idempotency_key="idem-client", client=FakeSupplierClient())

    assert result.supplier_activation_id.startswith("fake-sup-act-")
    assert result.phone_number.startswith("+")


def test_fake_supplier_send_sms_returns_manual_payload_without_callback_config(monkeypatch):
    monkeypatch.delenv("SMSBRIDGE_BASE_URL", raising=False)
    monkeypatch.delenv("SMSBRIDGE_SUPPLIER_API_KEY", raising=False)
    client = TestClient(app)

    response = client.post(
        "/v1/send-sms",
        json={
            "supplier_activation_id": "fake-sup-act-1",
            "phone_number": "+628123456789",
            "text": "Telegram code: 123456",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "manual"
    assert response.json()["payload"]["supplier_activation_id"] == "fake-sup-act-1"
