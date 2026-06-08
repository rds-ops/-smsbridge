from __future__ import annotations

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import BuyerApiKey


def _create_api_key(client, user_token: str, name: str = "local test") -> dict:
    response = client.post(
        "/api/v1/api-keys",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"name": name, "scopes": {"orders": "read_write"}},
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
    assert created["scopes"] == {"orders": "read_write"}
    assert "key_hash" not in created

    listed = client.get("/api/v1/api-keys", headers={"Authorization": f"Bearer {user_token}"})
    assert listed.status_code == 200, listed.text
    row = listed.json()[0]
    assert row["public_id"] == created["public_id"]
    assert "api_key" not in row
    assert "key_hash" not in row
    assert row["key_prefix"] == created["key_prefix"]


def test_new_api_key_authenticates_buyer_endpoint_and_updates_last_used(client, user_token):
    created = _create_api_key(client, user_token)

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
