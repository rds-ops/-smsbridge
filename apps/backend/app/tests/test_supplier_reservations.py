from __future__ import annotations

from decimal import Decimal

import httpx
import pytest

from app.models import Supplier
from app.services.supplier_reservations import (
    SupplierReservationError,
    SupplierReservationInvalidResponse,
    SupplierReservationRequest,
    SupplierReservationTimeout,
    SupplierReservationUnavailable,
    reserve_supplier_number,
)


def reservation_request() -> SupplierReservationRequest:
    return SupplierReservationRequest(
        request_id="sb-order-1",
        order_public_id="order-public-id",
        service_code="telegram",
        country_iso2="ID",
        operator=None,
        client_price=Decimal("0.5000"),
        supplier_reward=Decimal("0.3500"),
        timeout_seconds=120,
    )


def supplier(**kwargs) -> Supplier:
    defaults = {
        "name": "Reservation Supplier",
        "status": "active",
        "reservation_url": "https://supplier.example.test/v1/reservations",
        "reservation_auth_type": "none",
        "reservation_enabled": True,
    }
    defaults.update(kwargs)
    return Supplier(**defaults)


def client_for(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_successful_reservation_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "reserved",
                "supplier_activation_id": "sup_123",
                "phone_number": "+628123456789",
                "expires_at": "2026-05-29T12:10:00Z",
            },
        )

    result = reserve_supplier_number(
        supplier(),
        reservation_request(),
        idempotency_key="idem-1",
        client=client_for(handler),
    )

    assert result.supplier_activation_id == "sup_123"
    assert result.phone_number == "+628123456789"
    assert result.expires_at is not None


def test_bearer_auth_header_is_sent():
    seen_headers = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update(request.headers)
        return httpx.Response(200, json={"status": "reserved", "supplier_activation_id": "sup_123", "phone_number": "+628123456789"})

    reserve_supplier_number(
        supplier(reservation_auth_type="bearer", reservation_auth_secret_encrypted="enc:test-secret"),
        reservation_request(),
        idempotency_key="idem-1",
        client=client_for(handler),
    )

    assert seen_headers["authorization"] == "Bearer enc:test-secret"
    assert seen_headers["idempotency-key"] == "idem-1"


def test_none_auth_sends_no_authorization_header():
    seen_headers = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update(request.headers)
        return httpx.Response(200, json={"status": "reserved", "supplier_activation_id": "sup_123", "phone_number": "+628123456789"})

    reserve_supplier_number(
        supplier(reservation_auth_type="none"),
        reservation_request(),
        idempotency_key="idem-1",
        client=client_for(handler),
    )

    assert "authorization" not in seen_headers
    assert seen_headers["idempotency-key"] == "idem-1"


def test_timeout_raises_supplier_reservation_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    with pytest.raises(SupplierReservationTimeout):
        reserve_supplier_number(supplier(), reservation_request(), idempotency_key="idem-1", client=client_for(handler))


@pytest.mark.parametrize("status_code", [400, 404, 429, 500])
def test_http_error_raises_supplier_reservation_unavailable(status_code):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"status": "error"})

    with pytest.raises(SupplierReservationUnavailable):
        reserve_supplier_number(supplier(), reservation_request(), idempotency_key="idem-1", client=client_for(handler))


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, content=b"not-json"),
        httpx.Response(200, json={"status": "no_inventory"}),
        httpx.Response(200, json={"status": "reserved", "phone_number": "+628123456789"}),
        httpx.Response(200, json={"status": "reserved", "supplier_activation_id": "sup_123", "phone_number": "628123456789"}),
        httpx.Response(200, json={"status": "reserved", "supplier_activation_id": "sup_123", "phone_number": "+628123456789", "expires_at": 123}),
    ],
)
def test_invalid_response_raises_supplier_reservation_invalid_response(response):
    def handler(request: httpx.Request) -> httpx.Response:
        return response

    with pytest.raises(SupplierReservationInvalidResponse):
        reserve_supplier_number(supplier(), reservation_request(), idempotency_key="idem-1", client=client_for(handler))


def test_missing_reservation_url_raises_clear_error():
    with pytest.raises(SupplierReservationError, match="URL is not configured"):
        reserve_supplier_number(
            supplier(reservation_url=None),
            reservation_request(),
            idempotency_key="idem-1",
            client=client_for(lambda request: httpx.Response(500)),
        )


def test_disabled_reservation_raises_clear_error():
    with pytest.raises(SupplierReservationError, match="disabled"):
        reserve_supplier_number(
            supplier(reservation_enabled=False),
            reservation_request(),
            idempotency_key="idem-1",
            client=client_for(lambda request: httpx.Response(500)),
        )
