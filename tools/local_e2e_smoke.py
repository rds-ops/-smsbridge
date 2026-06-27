from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from contextlib import contextmanager
from typing import Any
from uuid import uuid4


BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
FAKE_SUPPLIER_URL = os.getenv("FAKE_SUPPLIER_URL", "http://localhost:8010").rstrip("/")
RESERVATION_URL_FOR_BACKEND = os.getenv(
    "RESERVATION_URL_FOR_BACKEND",
    "http://fake-supplier:8010/v1/reservations",
)
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@smsbridge.local")
BUYER_EMAIL = os.getenv("BUYER_EMAIL", "user@smsbridge.local")
PASSWORD = os.getenv("LOCAL_E2E_PASSWORD", "change-me")
RUN_ID = os.getenv("LOCAL_E2E_RUN_ID", uuid4().hex[:8])
HTTP_TIMEOUT_SECONDS = float(os.getenv("LOCAL_E2E_TIMEOUT_SECONDS", "15"))
SNIPPET_LIMIT = 500


class SmokeError(RuntimeError):
    pass


_current_step = "startup"


@contextmanager
def step(name: str):
    global _current_step
    previous_step = _current_step
    _current_step = name
    print(f"\n==> {name}")
    try:
        yield
    except SmokeError:
        raise
    except Exception as exc:
        raise SmokeError(f"step failed: {name}: {exc}") from exc
    finally:
        _current_step = previous_step


def request(
    method: str,
    path_or_url: str,
    *,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    url = path_or_url if path_or_url.startswith("http") else f"{BASE_URL}{path_or_url}"
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req_headers = {"Content-Type": "application/json"}
    if token:
        req_headers["Authorization"] = f"Bearer {token}"
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        detail = _safe_snippet(exc.read().decode("utf-8", errors="replace"))
        raise SmokeError(f"step={_current_step}; {method} {url} failed: HTTP {exc.code}; response={detail}") from exc
    except urllib.error.URLError as exc:
        raise SmokeError(f"step={_current_step}; {method} {url} failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise SmokeError(f"step={_current_step}; {method} {url} timed out after {HTTP_TIMEOUT_SECONDS}s") from exc


def _safe_snippet(value: str) -> str:
    value = value.replace("\n", " ").replace("\r", " ")
    if len(value) > SNIPPET_LIMIT:
        return value[:SNIPPET_LIMIT] + "..."
    return value


def login(email: str) -> str:
    data = request("POST", "/auth/login", payload={"email": email, "password": PASSWORD})
    if not isinstance(data, dict) or not data.get("access_token"):
        raise SmokeError(f"login for {email} did not return an access token")
    return data["access_token"]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeError(message)


def find_payment_id(payment_rows: list[dict[str, Any]], public_id: str) -> int:
    for row in payment_rows:
        if row.get("public_id") == public_id:
            return int(row["id"])
    raise SmokeError(f"admin payment-intents list did not include payment intent {public_id}")


def endpoint_available(url: str) -> bool:
    try:
        request("GET", url)
    except SmokeError:
        return False
    return True


def find_activation_by_phone(activation_rows: list[dict[str, Any]], phone_number: str) -> dict[str, Any]:
    for row in activation_rows:
        if row.get("phone_number") == phone_number:
            return row
    raise SmokeError(f"supplier activations did not include phone number {phone_number}; order was not supplier-backed")


def block_existing_active_suppliers(admin_token: str) -> int:
    blocked = 0
    for supplier in request("GET", "/admin/suppliers", token=admin_token):
        if supplier.get("status") != "active":
            continue
        request(
            "PATCH",
            f"/admin/suppliers/{supplier['id']}",
            token=admin_token,
            payload={"status": "blocked"},
        )
        blocked += 1
    return blocked


def main() -> int:
    print(f"BASE_URL={BASE_URL}")
    print(f"FAKE_SUPPLIER_URL={FAKE_SUPPLIER_URL}")
    print(f"RESERVATION_URL_FOR_BACKEND={RESERVATION_URL_FOR_BACKEND}")
    print(f"RUN_ID={RUN_ID}")
    print(f"HTTP_TIMEOUT_SECONDS={HTTP_TIMEOUT_SECONDS:g}")

    with step("health checks"):
        live = request("GET", "/health/live")
        ready = request("GET", "/health/ready")
        print("health:", live, ready)

    with step("login admin and buyer"):
        admin_token = login(ADMIN_EMAIL)
        buyer_token = login(BUYER_EMAIL)
        buyer = request("GET", "/auth/me", token=buyer_token)
        print("buyer:", {"id": buyer["id"], "email": buyer["email"]})

    with step("raise local buyer test limits"):
        limits = request(
            "PATCH",
            f"/admin/users/{buyer['id']}/limits",
            token=admin_token,
            payload={
                "tier": "verified",
                "max_orders_per_minute": 60,
                "max_orders_per_day": 1000,
                "max_active_orders": 1000,
                "max_daily_spend": "10000.0000",
            },
        )
        print("limits:", {"tier": limits["tier"], "max_active_orders": limits["limit"]["max_active_orders"]})

    with step("check fake supplier availability"):
        fake_supplier_available = endpoint_available(f"{FAKE_SUPPLIER_URL}/openapi.json")
        mode = "reservation callback" if fake_supplier_available else "local supplier fallback"
        print("fake supplier:", {"available": fake_supplier_available, "mode": mode})

    with step("isolate smoke supplier"):
        blocked_suppliers = block_existing_active_suppliers(admin_token)
        print("blocked existing active suppliers:", blocked_suppliers)

    with step("create supplier"):
        supplier_payload = {
            "name": f"Local Fake Supplier {RUN_ID}",
            "email": f"fake-supplier-{RUN_ID}@example.test",
            "status": "active",
            "reward_percent": "70.00",
        }
        if fake_supplier_available:
            supplier_payload.update(
                {
                    "reservation_enabled": True,
                    "reservation_url": RESERVATION_URL_FOR_BACKEND,
                    "reservation_auth_type": "none",
                    "reservation_timeout_seconds": 5,
                }
            )
        supplier = request(
            "POST",
            "/admin/suppliers",
            token=admin_token,
            payload=supplier_payload,
        )
        supplier_id = supplier["id"]
        key_response = request("POST", f"/admin/suppliers/{supplier_id}/api-key/regenerate", token=admin_token)
        supplier_key = key_response["api_key"]
        require(bool(supplier_key), "supplier API key was not returned")
        print(
            "supplier:",
            {
                "id": supplier_id,
                "reservation_enabled": supplier["reservation_enabled"],
                "reservation_url": supplier["reservation_url"],
            },
        )

    with step("update supplier inventory"):
        inventory = request(
            "POST",
            "/supplier/v1/inventory/update",
            token=supplier_key,
            payload={
                "items": [
                    {
                        "service_code": "telegram",
                        "country_iso2": "ID",
                        "operator": None,
                        "available_count": 10,
                        "success_rate": "95.00",
                        "avg_sms_time_seconds": 20,
                        "status": "active",
                    }
                ]
            },
        )
        print("inventory:", inventory)

    with step("create and manually complete payment intent"):
        payment = request(
            "POST",
            "/api/v1/payment-intents",
            token=buyer_token,
            headers={"Idempotency-Key": f"local-e2e-payment-{RUN_ID}"},
            payload={"amount": "10.0000", "provider": "manual_test", "currency": "USD"},
        )
        payment_rows = request("GET", "/admin/payment-intents?provider=manual_test&limit=100", token=admin_token)
        payment_id = find_payment_id(payment_rows, payment["public_id"])
        completed_payment = request("POST", f"/admin/payment-intents/{payment_id}/manual-complete", token=admin_token)
        require(completed_payment["status"] == "succeeded", "manual-complete did not succeed")
        print("payment:", {"public_id": payment["public_id"], "status": completed_payment["status"]})
        print("balance:", request("GET", "/api/v1/balance", token=buyer_token))

    with step("create supplier-backed order"):
        order = request(
            "POST",
            "/api/v1/orders",
            token=buyer_token,
            headers={"Idempotency-Key": f"local-e2e-order-{RUN_ID}"},
            payload={"service_code": "telegram", "country_iso2": "ID", "operator": None},
        )
        require(order["status"] == "waiting_sms", f"expected waiting_sms order, got {order['status']}")
        require(bool(order.get("phone_number")), "order did not include a phone number")
        activations = request("GET", f"/admin/suppliers/{supplier_id}/activations", token=admin_token)
        activation = find_activation_by_phone(activations, order["phone_number"])
        print(
            "order:",
            {
                "public_id": order["public_id"],
                "status": order["status"],
                "phone_number": order["phone_number"],
                "supplier_activation_id": activation.get("supplier_activation_id"),
            },
        )

    sms_payload = {
        "supplier_sms_id": f"local-e2e-sms-{RUN_ID}",
        "phone_number": order["phone_number"],
        "phone_from": "Telegram",
        "text": "Your Telegram code is 12345",
    }
    with step("push supplier SMS"):
        if fake_supplier_available:
            try:
                fake_sms = request("POST", f"{FAKE_SUPPLIER_URL}/v1/send-sms", payload=sms_payload)
                print("fake supplier sms helper:", fake_sms.get("status"))
            except Exception as exc:
                print(f"fake supplier sms helper failed; posting SMS directly. reason={_safe_snippet(str(exc))}")
        else:
            print("fake supplier sms helper skipped; using direct supplier API push")
        sms = request("POST", "/supplier/v1/sms", token=supplier_key, payload=sms_payload)
        print("supplier sms:", sms)

    with step("verify SMS and finish order"):
        order_after_sms = request("GET", f"/api/v1/orders/{order['public_id']}", token=buyer_token)
        require(order_after_sms["status"] == "sms_received", f"expected sms_received, got {order_after_sms['status']}")
        require(order_after_sms["sms_code"] == "12345", f"expected sms code 12345, got {order_after_sms['sms_code']}")
        print("order after sms:", {"status": order_after_sms["status"], "sms_code": order_after_sms["sms_code"]})

        finished = request("POST", f"/api/v1/orders/{order['public_id']}/finish", token=buyer_token)
        require(finished["status"] == "completed", f"expected completed, got {finished['status']}")
        print("finished order:", {"status": finished["status"], "public_id": finished["public_id"]})

    with step("print wallet and supplier ledgers"):
        print("wallet transactions:", request("GET", "/api/v1/wallet/transactions?limit=10", token=buyer_token))
        print("supplier transactions:", request("GET", f"/admin/suppliers/{supplier_id}/transactions", token=admin_token))
    print("OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as exc:
        print(f"\nERROR: step={_current_step}; unexpected failure: {exc}", file=sys.stderr)
        raise SystemExit(1)
