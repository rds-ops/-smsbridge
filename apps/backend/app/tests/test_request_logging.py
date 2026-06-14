from __future__ import annotations

import json
import logging

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import ApiRequestLog


def _latest_log(endpoint: str) -> ApiRequestLog:
    with SessionLocal() as db:
        log = db.scalar(
            select(ApiRequestLog)
            .where(ApiRequestLog.endpoint == endpoint)
            .order_by(ApiRequestLog.created_at.desc(), ApiRequestLog.id.desc())
        )
        assert log is not None
        return log


def test_response_includes_generated_request_id(client, user_token):
    response = client.get("/api/v1/balance", headers={"Authorization": f"Bearer {user_token}"})

    assert response.status_code == 200, response.text
    request_id = response.headers.get("X-Request-ID")
    assert request_id
    assert len(request_id) <= 128

    log = _latest_log("/api/v1/balance")
    assert log.request_id == request_id


def test_valid_incoming_request_id_is_preserved(client, user_token):
    request_id = "beta-client_123.trace-1"

    response = client.get(
        "/api/v1/balance",
        headers={"Authorization": f"Bearer {user_token}", "X-Request-ID": request_id},
    )

    assert response.status_code == 200, response.text
    assert response.headers["X-Request-ID"] == request_id
    assert _latest_log("/api/v1/balance").request_id == request_id


def test_unsafe_or_too_long_request_id_is_replaced(client, user_token):
    unsafe_request_id = "x" * 129

    response = client.get(
        "/api/v1/balance",
        headers={"Authorization": f"Bearer {user_token}", "X-Request-ID": unsafe_request_id},
    )

    assert response.status_code == 200, response.text
    returned_request_id = response.headers["X-Request-ID"]
    assert returned_request_id != unsafe_request_id
    assert len(returned_request_id) <= 128
    assert _latest_log("/api/v1/balance").request_id == returned_request_id


def test_structured_request_log_uses_safe_context_only(client, caplog):
    request_id = "login-safe-context"
    password = "do-not-log-this-password"

    with caplog.at_level(logging.INFO, logger="smsbridge.requests"):
        response = client.post(
            "/auth/login",
            headers={"X-Request-ID": request_id, "Authorization": "Bearer do-not-log-this-token"},
            json={"email": "missing@example.com", "password": password},
        )

    assert response.status_code == 401
    log = _latest_log("/auth/login")
    assert log.request_id == request_id
    assert log.endpoint == "/auth/login"
    assert log.method == "POST"
    assert "do-not-log-this-token" not in str(log.__dict__)
    assert password not in str(log.__dict__)

    records = [record for record in caplog.records if record.name == "smsbridge.requests"]
    assert records
    payload = json.loads(records[-1].message)
    assert payload == {
        "buyer_api_key_id": None,
        "endpoint": "/auth/login",
        "event": "request_completed",
        "method": "POST",
        "request_id": request_id,
        "status_code": 401,
        "supplier_id": None,
        "user_id": None,
    }
    assert "do-not-log-this-token" not in records[-1].message
    assert password not in records[-1].message


def test_admin_can_filter_api_request_logs_by_request_id(client, admin_token, user_token):
    first = client.get(
        "/api/v1/balance",
        headers={"Authorization": f"Bearer {user_token}", "X-Request-ID": "filter-request-a"},
    )
    second = client.get(
        "/api/v1/limits",
        headers={"Authorization": f"Bearer {user_token}", "X-Request-ID": "filter-request-b"},
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text

    response = client.get(
        "/admin/api-request-logs?request_id=filter-request-a",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 1
    assert body[0]["request_id"] == "filter-request-a"
    assert body[0]["endpoint"] == "/api/v1/balance"
    assert "filter-request-b" not in str(body)


def test_non_admin_cannot_access_api_request_logs(client, user_token):
    response = client.get("/admin/api-request-logs", headers={"Authorization": f"Bearer {user_token}"})
    assert response.status_code == 403


def test_admin_api_request_log_method_status_and_endpoint_filters(client, admin_token, user_token):
    ok = client.get(
        "/api/v1/balance",
        headers={"Authorization": f"Bearer {user_token}", "X-Request-ID": "filter-status-ok"},
    )
    missing = client.get(
        "/api/v1/orders/missing-order",
        headers={"Authorization": f"Bearer {user_token}", "X-Request-ID": "filter-status-missing"},
    )
    assert ok.status_code == 200, ok.text
    assert missing.status_code == 404, missing.text

    response = client.get(
        "/admin/api-request-logs?method=GET&status_code=404&endpoint=/api/v1/orders/missing-order",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 1
    assert body[0]["request_id"] == "filter-status-missing"
    assert body[0]["method"] == "GET"
    assert body[0]["status_code"] == 404
    assert body[0]["endpoint"] == "/api/v1/orders/missing-order"


def test_admin_api_request_log_limit_and_offset(client, admin_token, user_token):
    for index in range(3):
        response = client.get(
            "/api/v1/balance",
            headers={"Authorization": f"Bearer {user_token}", "X-Request-ID": f"filter-page-{index}"},
        )
        assert response.status_code == 200, response.text

    first_page = client.get(
        "/admin/api-request-logs?endpoint=/api/v1/balance&limit=1&offset=0",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    second_page = client.get(
        "/admin/api-request-logs?endpoint=/api/v1/balance&limit=1&offset=1",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert first_page.status_code == 200, first_page.text
    assert second_page.status_code == 200, second_page.text
    assert len(first_page.json()) == 1
    assert len(second_page.json()) == 1
    assert first_page.json()[0]["id"] != second_page.json()[0]["id"]
