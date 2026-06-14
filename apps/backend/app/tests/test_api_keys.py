from __future__ import annotations

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import ApiRequestLog, BuyerApiKey, Country, Service


def _create_api_key(client, user_token: str, name: str = "local test", scopes: list[str] | None = None) -> dict:
    payload = {"name": name}
    if scopes is not None:
        payload["scopes"] = scopes
    response = client.post(
        "/api/v1/api-keys",
        headers={"Authorization": f"Bearer {user_token}"},
        json=payload,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _register_and_login(client, email: str) -> str:
    registered = client.post("/auth/register", json={"email": email, "password": "change-me"})
    assert registered.status_code == 200, registered.text
    logged_in = client.post("/auth/login", json={"email": email, "password": "change-me"})
    assert logged_in.status_code == 200, logged_in.text
    return logged_in.json()["access_token"]


def test_create_api_key_returns_raw_key_once(client, user_token):
    created = _create_api_key(client, user_token)

    assert created["api_key"].startswith("sb_live_")
    assert created["key_prefix"] == created["api_key"][:16]
    assert created["name"] == "local test"
    assert created["status"] == "active"
    assert "wallet:read" in created["scopes"]
    assert "orders:create" in created["scopes"]
    assert "key_hash" not in created

    listed = client.get("/api/v1/api-keys", headers={"Authorization": f"Bearer {user_token}"})
    assert listed.status_code == 200, listed.text
    row = listed.json()[0]
    assert row["public_id"] == created["public_id"]
    assert "api_key" not in row
    assert "key_hash" not in row
    assert row["key_prefix"] == created["key_prefix"]


def test_new_api_key_authenticates_buyer_endpoint_and_updates_last_used(client, user_token):
    created = _create_api_key(client, user_token, scopes=["wallet:read"])

    before = client.get("/api/v1/api-keys", headers={"Authorization": f"Bearer {user_token}"}).json()[0]
    assert before["last_used_at"] is None

    balance = client.get("/api/v1/balance", headers={"Authorization": f"Bearer {created['api_key']}"})
    assert balance.status_code == 200, balance.text

    after = client.get("/api/v1/api-keys", headers={"Authorization": f"Bearer {user_token}"}).json()[0]
    assert after["last_used_at"] is not None


def test_revoked_api_key_no_longer_authenticates_and_revoke_is_idempotent(client, user_token):
    created = _create_api_key(client, user_token)

    first = client.post(
        f"/api/v1/api-keys/{created['public_id']}/revoke",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "revoked"
    assert first.json()["revoked_at"] is not None

    second = client.post(
        f"/api/v1/api-keys/{created['public_id']}/revoke",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert second.status_code == 200, second.text
    assert second.json()["status"] == "revoked"
    assert second.json()["revoked_at"] == first.json()["revoked_at"]

    rejected = client.get("/api/v1/balance", headers={"Authorization": f"Bearer {created['api_key']}"})
    assert rejected.status_code == 401


def test_legacy_api_key_auth_still_works(client, user_token):
    legacy = client.post("/api/v1/api-key/regenerate", headers={"Authorization": f"Bearer {user_token}"})
    assert legacy.status_code == 200, legacy.text

    response = client.get("/api/v1/balance", headers={"Authorization": f"Bearer {legacy.json()['api_key']}"})
    assert response.status_code == 200, response.text


def test_user_cannot_manage_another_users_api_keys(client, user_token):
    other_token = _register_and_login(client, "other-api-key-user@example.com")
    other_key = _create_api_key(client, other_token, "other")

    listed = client.get("/api/v1/api-keys", headers={"Authorization": f"Bearer {user_token}"})
    assert listed.status_code == 200, listed.text
    assert all(row["public_id"] != other_key["public_id"] for row in listed.json())

    revoke = client.post(
        f"/api/v1/api-keys/{other_key['public_id']}/revoke",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert revoke.status_code == 404

    still_works = client.get("/api/v1/balance", headers={"Authorization": f"Bearer {other_key['api_key']}"})
    assert still_works.status_code == 200, still_works.text


def test_api_key_hash_is_stored_without_raw_key(client, user_token):
    created = _create_api_key(client, user_token)

    with SessionLocal() as db:
        api_key = db.scalar(select(BuyerApiKey).where(BuyerApiKey.public_id == created["public_id"]))
        assert api_key is not None
        assert api_key.key_hash != created["api_key"]
        assert created["api_key"] not in api_key.key_hash


def test_managed_api_key_request_logs_buyer_api_key_id(client, user_token):
    created = _create_api_key(client, user_token, scopes=["wallet:read"])

    response = client.get("/api/v1/balance", headers={"Authorization": f"Bearer {created['api_key']}"})
    assert response.status_code == 200, response.text

    with SessionLocal() as db:
        api_key = db.scalar(select(BuyerApiKey).where(BuyerApiKey.public_id == created["public_id"]))
        log = db.scalar(
            select(ApiRequestLog)
            .where(ApiRequestLog.endpoint == "/api/v1/balance", ApiRequestLog.status_code == 200)
            .order_by(ApiRequestLog.created_at.desc(), ApiRequestLog.id.desc())
        )
        assert log is not None
        assert log.user_id == api_key.user_id
        assert log.buyer_api_key_id == api_key.id
        assert log.supplier_id is None


def test_legacy_api_key_request_logs_without_buyer_api_key_id(client, user_token):
    legacy = client.post("/api/v1/api-key/regenerate", headers={"Authorization": f"Bearer {user_token}"})
    assert legacy.status_code == 200, legacy.text

    response = client.get("/api/v1/balance", headers={"Authorization": f"Bearer {legacy.json()['api_key']}"})
    assert response.status_code == 200, response.text

    with SessionLocal() as db:
        log = db.scalar(
            select(ApiRequestLog)
            .where(ApiRequestLog.endpoint == "/api/v1/balance", ApiRequestLog.status_code == 200)
            .order_by(ApiRequestLog.created_at.desc(), ApiRequestLog.id.desc())
        )
        assert log is not None
        assert log.user_id == 2
        assert log.buyer_api_key_id is None


def test_buyer_can_view_own_api_key_usage_without_raw_secret(client, user_token):
    created = _create_api_key(client, user_token, scopes=["wallet:read"])
    assert client.get("/api/v1/balance", headers={"Authorization": f"Bearer {created['api_key']}"}).status_code == 200
    assert client.get("/api/v1/limits", headers={"Authorization": f"Bearer {created['api_key']}"}).status_code == 200

    response = client.get(
        f"/api/v1/api-keys/{created['public_id']}/usage",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["public_id"] == created["public_id"]
    assert body["key_prefix"] == created["key_prefix"]
    assert body["total_requests"] == 2
    assert body["last_used_at"] is not None
    assert {"endpoint": "/api/v1/balance", "method": "GET", "status_code": 200, "count": 1} in body["recent"]
    assert {"endpoint": "/api/v1/limits", "method": "GET", "status_code": 200, "count": 1} in body["recent"]
    assert "api_key" not in body
    assert "key_hash" not in body
    assert created["api_key"] not in str(body)


def test_buyer_cannot_view_another_users_api_key_usage(client, user_token):
    other_token = _register_and_login(client, "usage-other@example.com")
    other_key = _create_api_key(client, other_token, "other usage")

    response = client.get(
        f"/api/v1/api-keys/{other_key['public_id']}/usage",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 404


def test_revoked_key_usage_visible_but_revoked_key_cannot_authenticate(client, user_token):
    created = _create_api_key(client, user_token, scopes=["wallet:read"])
    assert client.get("/api/v1/balance", headers={"Authorization": f"Bearer {created['api_key']}"}).status_code == 200
    revoked = client.post(
        f"/api/v1/api-keys/{created['public_id']}/revoke",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert revoked.status_code == 200, revoked.text

    rejected = client.get("/api/v1/balance", headers={"Authorization": f"Bearer {created['api_key']}"})
    assert rejected.status_code == 401

    usage = client.get(
        f"/api/v1/api-keys/{created['public_id']}/usage",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert usage.status_code == 200, usage.text
    assert usage.json()["status"] == "revoked"
    assert usage.json()["total_requests"] == 1


def test_jwt_buyer_access_still_works_without_api_key_scopes(client, user_token):
    response = client.get("/api/v1/balance", headers={"Authorization": f"Bearer {user_token}"})
    assert response.status_code == 200, response.text


def test_jwt_buyer_can_read_catalog(client, user_token):
    services = client.get("/api/v1/services", headers={"Authorization": f"Bearer {user_token}"})
    countries = client.get("/api/v1/countries", headers={"Authorization": f"Bearer {user_token}"})

    assert services.status_code == 200, services.text
    assert countries.status_code == 200, countries.text
    assert any(row["code"] == "telegram" for row in services.json())
    assert any(row["iso2"] == "ID" for row in countries.json())


def test_managed_api_key_with_read_scope_can_read_catalog(client, user_token):
    created = _create_api_key(client, user_token, scopes=["read"])

    services = client.get("/api/v1/services", headers={"Authorization": f"Bearer {created['api_key']}"})
    countries = client.get("/api/v1/countries", headers={"Authorization": f"Bearer {created['api_key']}"})

    assert services.status_code == 200, services.text
    assert countries.status_code == 200, countries.text
    assert any(row["code"] == "telegram" for row in services.json())
    assert any(row["iso2"] == "ID" for row in countries.json())


def test_legacy_api_key_can_read_catalog(client, user_token):
    legacy = client.post("/api/v1/api-key/regenerate", headers={"Authorization": f"Bearer {user_token}"})
    assert legacy.status_code == 200, legacy.text

    services = client.get("/api/v1/services", headers={"Authorization": f"Bearer {legacy.json()['api_key']}"})
    countries = client.get("/api/v1/countries", headers={"Authorization": f"Bearer {legacy.json()['api_key']}"})

    assert services.status_code == 200, services.text
    assert countries.status_code == 200, countries.text


def test_catalog_requires_valid_buyer_auth(client):
    missing = client.get("/api/v1/services")
    invalid = client.get("/api/v1/countries", headers={"Authorization": "Bearer invalid"})

    assert missing.status_code == 401
    assert invalid.status_code == 401


def test_managed_api_key_without_read_scope_cannot_read_catalog(client, user_token):
    created = _create_api_key(client, user_token, scopes=["wallet:read"])

    services = client.get("/api/v1/services", headers={"Authorization": f"Bearer {created['api_key']}"})
    countries = client.get("/api/v1/countries", headers={"Authorization": f"Bearer {created['api_key']}"})

    assert services.status_code == 403
    assert countries.status_code == 403
    assert services.json()["detail"] == "API key scope is not allowed"
    assert countries.json()["detail"] == "API key scope is not allowed"


def test_catalog_returns_only_active_services_and_countries(client, user_token):
    with SessionLocal() as db:
        db.add(Service(code="inactive_test", name_en="Inactive", name_ru="Неактивный", is_active=False))
        db.add(Country(iso2="ZZ", name_en="Inactive Country", name_ru="Неактивная страна", is_active=False))
        db.commit()

    services = client.get("/api/v1/services", headers={"Authorization": f"Bearer {user_token}"})
    countries = client.get("/api/v1/countries", headers={"Authorization": f"Bearer {user_token}"})

    assert services.status_code == 200, services.text
    assert countries.status_code == 200, countries.text
    assert all(row["code"] != "inactive_test" for row in services.json())
    assert all(row["iso2"] != "ZZ" for row in countries.json())


def test_managed_key_without_wallet_read_cannot_read_balance(client, user_token):
    created = _create_api_key(client, user_token, scopes=["orders:create"])
    response = client.get("/api/v1/balance", headers={"Authorization": f"Bearer {created['api_key']}"})
    assert response.status_code == 403
    assert response.json()["detail"] == "API key scope is not allowed"


def test_managed_key_with_orders_create_can_create_order(client, user_token):
    created = _create_api_key(client, user_token, scopes=["orders:create"])
    response = client.post(
        "/api/v1/orders",
        headers={"Authorization": f"Bearer {created['api_key']}"},
        json={"service_code": "telegram", "country_iso2": "ID"},
    )
    assert response.status_code == 200, response.text


def test_managed_key_without_orders_create_cannot_create_order(client, user_token):
    created = _create_api_key(client, user_token, scopes=["wallet:read"])
    response = client.post(
        "/api/v1/orders",
        headers={"Authorization": f"Bearer {created['api_key']}"},
        json={"service_code": "telegram", "country_iso2": "ID"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "API key scope is not allowed"


def test_api_key_management_endpoints_remain_jwt_only(client, user_token):
    created = _create_api_key(client, user_token)
    response = client.get("/api/v1/api-keys", headers={"Authorization": f"Bearer {created['api_key']}"})
    assert response.status_code == 401
