from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

import httpx

from app.models import Supplier

DEFAULT_RESERVATION_TIMEOUT_SECONDS = 5


class SupplierReservationError(Exception):
    pass


class SupplierReservationTimeout(SupplierReservationError):
    pass


class SupplierReservationInvalidResponse(SupplierReservationError):
    pass


class SupplierReservationUnavailable(SupplierReservationError):
    pass


@dataclass(frozen=True)
class SupplierReservationRequest:
    request_id: str
    order_public_id: str
    service_code: str
    country_iso2: str
    operator: str | None
    client_price: Decimal
    supplier_reward: Decimal
    timeout_seconds: int

    def payload(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "order_public_id": self.order_public_id,
            "service_code": self.service_code,
            "country_iso2": self.country_iso2,
            "operator": self.operator,
            "client_price": str(self.client_price),
            "supplier_reward": str(self.supplier_reward),
            "timeout_seconds": self.timeout_seconds,
        }


@dataclass(frozen=True)
class SupplierReservationResult:
    supplier_activation_id: str
    phone_number: str
    expires_at: datetime | None = None


@dataclass(frozen=True)
class SupplierReleaseRequest:
    request_id: str
    order_public_id: str
    supplier_activation_id: str
    phone_number: str
    reason: str
    timestamp: datetime

    def payload(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "order_public_id": self.order_public_id,
            "supplier_activation_id": self.supplier_activation_id,
            "phone_number": self.phone_number,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
        }


def reserve_supplier_number(
    supplier: Supplier,
    request: SupplierReservationRequest,
    *,
    idempotency_key: str,
    client: httpx.Client | None = None,
) -> SupplierReservationResult:
    if not supplier.reservation_enabled:
        raise SupplierReservationError("Supplier reservation is disabled")
    if not supplier.reservation_url:
        raise SupplierReservationError("Supplier reservation URL is not configured")

    timeout_seconds = supplier.reservation_timeout_seconds or DEFAULT_RESERVATION_TIMEOUT_SECONDS
    headers = {"Idempotency-Key": idempotency_key}
    auth_type = (supplier.reservation_auth_type or "none").lower()
    if auth_type == "bearer":
        secret = supplier.reservation_auth_secret_encrypted
        if not secret:
            raise SupplierReservationError("Supplier reservation bearer auth is not configured")
        headers["Authorization"] = f"Bearer {secret}"
    elif auth_type != "none":
        raise SupplierReservationError("Unsupported supplier reservation auth type")

    owns_client = client is None
    http_client = client or httpx.Client(timeout=timeout_seconds)
    try:
        try:
            response = http_client.post(
                supplier.reservation_url,
                json=request.payload(),
                headers=headers,
                timeout=timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise SupplierReservationTimeout("Supplier reservation request timed out") from exc
        except httpx.RequestError as exc:
            raise SupplierReservationUnavailable("Supplier reservation request failed") from exc

        if response.status_code >= 400:
            raise SupplierReservationUnavailable(f"Supplier reservation returned HTTP {response.status_code}")

        try:
            data = response.json()
        except ValueError as exc:
            raise SupplierReservationInvalidResponse("Supplier reservation response was not valid JSON") from exc

        return _parse_reservation_response(data)
    finally:
        if owns_client:
            http_client.close()


def release_supplier_number(
    supplier: Supplier,
    request: SupplierReleaseRequest,
    *,
    idempotency_key: str,
    client: httpx.Client | None = None,
) -> None:
    if not supplier.reservation_enabled:
        raise SupplierReservationError("Supplier reservation is disabled")
    if not supplier.reservation_url:
        raise SupplierReservationError("Supplier reservation URL is not configured")

    timeout_seconds = supplier.reservation_timeout_seconds or DEFAULT_RESERVATION_TIMEOUT_SECONDS
    headers = {"Idempotency-Key": idempotency_key}
    auth_type = (supplier.reservation_auth_type or "none").lower()
    if auth_type == "bearer":
        secret = supplier.reservation_auth_secret_encrypted
        if not secret:
            raise SupplierReservationError("Supplier reservation bearer auth is not configured")
        headers["Authorization"] = f"Bearer {secret}"
    elif auth_type != "none":
        raise SupplierReservationError("Unsupported supplier reservation auth type")

    owns_client = client is None
    http_client = client or httpx.Client(timeout=timeout_seconds)
    try:
        try:
            response = http_client.post(
                _release_url(supplier.reservation_url),
                json=request.payload(),
                headers=headers,
                timeout=timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise SupplierReservationTimeout("Supplier release request timed out") from exc
        except httpx.RequestError as exc:
            raise SupplierReservationUnavailable("Supplier release request failed") from exc

        if response.status_code >= 400:
            raise SupplierReservationUnavailable(f"Supplier release returned HTTP {response.status_code}")
    finally:
        if owns_client:
            http_client.close()


def _release_url(reservation_url: str) -> str:
    stripped = reservation_url.rstrip("/")
    if stripped.endswith("/reservations"):
        return f"{stripped[: -len('/reservations')]}/release"
    return f"{stripped}/release"


def _parse_reservation_response(data: Any) -> SupplierReservationResult:
    if not isinstance(data, dict):
        raise SupplierReservationInvalidResponse("Supplier reservation response must be a JSON object")
    if data.get("status") != "reserved":
        raise SupplierReservationInvalidResponse("Supplier reservation response status must be reserved")

    supplier_activation_id = data.get("supplier_activation_id")
    if not isinstance(supplier_activation_id, str) or not supplier_activation_id.strip():
        raise SupplierReservationInvalidResponse("Supplier reservation response missing supplier_activation_id")

    phone_number = data.get("phone_number")
    if not isinstance(phone_number, str) or not phone_number.strip() or not phone_number.startswith("+"):
        raise SupplierReservationInvalidResponse("Supplier reservation response has invalid phone_number")

    expires_at = data.get("expires_at")
    parsed_expires_at = None
    if expires_at is not None:
        if not isinstance(expires_at, str):
            raise SupplierReservationInvalidResponse("Supplier reservation response has invalid expires_at")
        try:
            parsed_expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise SupplierReservationInvalidResponse("Supplier reservation response has invalid expires_at") from exc

    return SupplierReservationResult(
        supplier_activation_id=supplier_activation_id,
        phone_number=phone_number,
        expires_at=parsed_expires_at,
    )
