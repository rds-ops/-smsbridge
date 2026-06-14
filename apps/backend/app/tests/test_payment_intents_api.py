from __future__ import annotations

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import PaymentIntent


def test_create_payment_intent(client, user_token):
    response = client.post(
        "/api/v1/payment-intents",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"amount": "10.5000", "provider": "manual_test", "currency": "USD"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider"] == "manual_test"
    assert body["amount"] == "10.5000"
    assert body["status"] == "created"
    assert body["currency"] == "USD"
    assert body["public_id"]


def test_buyer_can_list_own_payment_intents(client, user_token):
    first = client.post(
        "/api/v1/payment-intents",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"amount": "10.0000", "provider": "manual_test", "currency": "USD"},
    )
    second = client.post(
        "/api/v1/payment-intents",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"amount": "11.0000", "provider": "manual_test", "currency": "USD"},
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text

    response = client.get("/api/v1/payment-intents", headers={"Authorization": f"Bearer {user_token}"})
    assert response.status_code == 200, response.text
    body = response.json()

    assert [item["public_id"] for item in body[:2]] == [second.json()["public_id"], first.json()["public_id"]]
    assert body[0]["amount"] == "11.0000"
    assert set(body[0]) == {"public_id", "provider", "currency", "amount", "status", "expires_at", "created_at"}


def test_payment_intent_list_does_not_include_other_users_intents(client, user_token):
    own = client.post(
        "/api/v1/payment-intents",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"amount": "6.0000", "provider": "manual_test"},
    )
    assert own.status_code == 200, own.text

    register = client.post(
        "/auth/register",
        json={"email": "payment-list-other@example.com", "password": "change-me", "locale": "en"},
    )
    assert register.status_code == 200, register.text
    other_token = register.json()["access_token"]

    other = client.post(
        "/api/v1/payment-intents",
        headers={"Authorization": f"Bearer {other_token}"},
        json={"amount": "9.0000", "provider": "manual_test"},
    )
    assert other.status_code == 200, other.text

    response = client.get("/api/v1/payment-intents", headers={"Authorization": f"Bearer {user_token}"})
    assert response.status_code == 200, response.text
    public_ids = {item["public_id"] for item in response.json()}

    assert own.json()["public_id"] in public_ids
    assert other.json()["public_id"] not in public_ids


def test_payment_intent_list_limit_offset(client, user_token):
    created = []
    for amount in ["1.0000", "2.0000", "3.0000"]:
        response = client.post(
            "/api/v1/payment-intents",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"amount": amount, "provider": "manual_test"},
        )
        assert response.status_code == 200, response.text
        created.append(response.json())

    response = client.get("/api/v1/payment-intents?limit=1&offset=1", headers={"Authorization": f"Bearer {user_token}"})
    assert response.status_code == 200, response.text
    body = response.json()

    assert len(body) == 1
    assert body[0]["public_id"] == created[-2]["public_id"]


def test_payment_intent_list_requires_auth(client):
    response = client.get("/api/v1/payment-intents")
    assert response.status_code == 401


def test_payment_intent_list_api_key_auth_supported(client, user_token):
    regen = client.post("/api/v1/api-key/regenerate", headers={"Authorization": f"Bearer {user_token}"})
    assert regen.status_code == 200, regen.text
    api_key = regen.json()["api_key"]

    create = client.post(
        "/api/v1/payment-intents",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"amount": "2.0000", "provider": "manual_test"},
    )
    assert create.status_code == 200, create.text

    response = client.get("/api/v1/payment-intents", headers={"Authorization": f"Bearer {api_key}"})
    assert response.status_code == 200, response.text
    assert response.json()[0]["public_id"] == create.json()["public_id"]


def test_payment_intent_amount_must_be_positive(client, user_token):
    response = client.post(
        "/api/v1/payment-intents",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"amount": "0", "provider": "manual_test"},
    )
    assert response.status_code == 422


def test_payment_intent_idempotent_same_body_returns_same_intent(client, user_token):
    headers = {"Authorization": f"Bearer {user_token}", "Idempotency-Key": "payment-intent-1"}
    payload = {"amount": "7.0000", "provider": "manual_test", "currency": "USD"}

    first = client.post("/api/v1/payment-intents", headers=headers, json=payload)
    second = client.post("/api/v1/payment-intents", headers=headers, json=payload)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["public_id"] == second.json()["public_id"]

    db = SessionLocal()
    try:
        assert (
            len(
                list(
                    db.scalars(
                        select(PaymentIntent).where(
                            PaymentIntent.user_id == 2,
                            PaymentIntent.idempotency_key == "payment-intent-1",
                        )
                    )
                )
            )
            == 1
        )
    finally:
        db.close()


def test_payment_intent_idempotent_different_body_returns_409(client, user_token):
    headers = {"Authorization": f"Bearer {user_token}", "Idempotency-Key": "payment-intent-2"}
    first = client.post(
        "/api/v1/payment-intents",
        headers=headers,
        json={"amount": "5.0000", "provider": "manual_test", "currency": "USD"},
    )
    second = client.post(
        "/api/v1/payment-intents",
        headers=headers,
        json={"amount": "9.0000", "provider": "manual_test", "currency": "USD"},
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 409, second.text


def test_different_users_can_reuse_same_idempotency_key(client, admin_token, user_token):
    key = "shared-payment-key"
    first = client.post(
        "/api/v1/payment-intents",
        headers={"Authorization": f"Bearer {user_token}", "Idempotency-Key": key},
        json={"amount": "3.0000", "provider": "manual_test"},
    )
    assert first.status_code == 200, first.text

    register = client.post(
        "/auth/register",
        json={"email": "intent-user@example.com", "password": "change-me", "locale": "en"},
    )
    assert register.status_code == 200, register.text
    second_token = register.json()["access_token"]

    second = client.post(
        "/api/v1/payment-intents",
        headers={"Authorization": f"Bearer {second_token}", "Idempotency-Key": key},
        json={"amount": "4.0000", "provider": "manual_test"},
    )
    assert second.status_code == 200, second.text
    assert second.json()["public_id"] != first.json()["public_id"]


def test_buyer_cannot_fetch_other_users_payment_intent(client, user_token):
    first = client.post(
        "/api/v1/payment-intents",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"amount": "8.0000", "provider": "manual_test"},
    )
    assert first.status_code == 200, first.text
    public_id = first.json()["public_id"]

    register = client.post(
        "/auth/register",
        json={"email": "intent-other@example.com", "password": "change-me", "locale": "en"},
    )
    assert register.status_code == 200, register.text
    other_token = register.json()["access_token"]

    get_other = client.get(
        f"/api/v1/payment-intents/{public_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert get_other.status_code == 404, get_other.text


def test_payment_intent_creation_does_not_credit_wallet(client, user_token):
    before = client.get("/api/v1/balance", headers={"Authorization": f"Bearer {user_token}"})
    assert before.status_code == 200, before.text

    create = client.post(
        "/api/v1/payment-intents",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"amount": "12.0000", "provider": "manual_test"},
    )
    assert create.status_code == 200, create.text

    after = client.get("/api/v1/balance", headers={"Authorization": f"Bearer {user_token}"})
    assert after.status_code == 200, after.text
    assert after.json()["balance"] == before.json()["balance"]
    assert after.json()["held_balance"] == before.json()["held_balance"]


def test_payment_intent_api_key_auth_supported(client, user_token):
    regen = client.post("/api/v1/api-key/regenerate", headers={"Authorization": f"Bearer {user_token}"})
    assert regen.status_code == 200, regen.text
    api_key = regen.json()["api_key"]

    create = client.post(
        "/api/v1/payment-intents",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"amount": "2.5000", "provider": "manual_test"},
    )
    assert create.status_code == 200, create.text

    get_one = client.get(
        f"/api/v1/payment-intents/{create.json()['public_id']}",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    assert get_one.status_code == 200, get_one.text
