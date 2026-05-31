from __future__ import annotations

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import PaymentIntent, PaymentWebhookEvent, WalletTransaction


def create_payment_intent(client, token: str, amount: str = "10.0000") -> dict:
    response = client.post(
        "/api/v1/payment-intents",
        headers={"Authorization": f"Bearer {token}"},
        json={"amount": amount, "provider": "manual_test", "currency": "USD"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def wallet_snapshot(client, token: str) -> dict:
    response = client.get("/api/v1/balance", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    return response.json()


def webhook_payload(public_id: str, status: str, event_id: str = "evt-1") -> dict:
    return {
        "event_id": event_id,
        "payment_intent_public_id": public_id,
        "status": status,
    }


def test_admin_can_list_and_fetch_payment_intents(client, admin_token, user_token):
    intent = create_payment_intent(client, user_token)

    listed = client.get("/admin/payment-intents", headers={"Authorization": f"Bearer {admin_token}"})
    assert listed.status_code == 200, listed.text
    assert listed.json()[0]["public_id"] == intent["public_id"]
    assert "metadata" in listed.json()[0]

    detail = client.get(f"/admin/payment-intents/{listed.json()[0]['id']}", headers={"Authorization": f"Bearer {admin_token}"})
    assert detail.status_code == 200, detail.text
    assert detail.json()["public_id"] == intent["public_id"]
    assert detail.json()["idempotency_key"] is None


def test_admin_payment_intent_filters(client, admin_token, user_token):
    create_payment_intent(client, user_token, amount="3.0000")
    response = client.get(
        "/admin/payment-intents?status=created&provider=manual_test&user_id=2&limit=10&offset=0",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    assert len(response.json()) == 1


def test_non_admin_blocked_from_payment_intent_admin(client, user_token):
    response = client.get("/admin/payment-intents", headers={"Authorization": f"Bearer {user_token}"})
    assert response.status_code == 403


def test_payment_webhook_requires_secret(client, user_token):
    intent = create_payment_intent(client, user_token)
    response = client.post("/internal/payment-webhooks/manual_test", json=webhook_payload(intent["public_id"], "pending"))
    assert response.status_code == 403


def test_payment_webhook_invalid_secret_rejected(client, user_token):
    intent = create_payment_intent(client, user_token)
    response = client.post(
        "/internal/payment-webhooks/manual_test",
        headers={"X-Internal-Webhook-Secret": "wrong"},
        json=webhook_payload(intent["public_id"], "pending"),
    )
    assert response.status_code == 403


def test_payment_webhook_valid_transitions_and_no_wallet_credit(client, user_token):
    intent = create_payment_intent(client, user_token)
    before = wallet_snapshot(client, user_token)

    pending = client.post(
        "/internal/payment-webhooks/manual_test",
        headers={"X-Internal-Webhook-Secret": "change-me"},
        json=webhook_payload(intent["public_id"], "pending", "evt-pending"),
    )
    assert pending.status_code == 200, pending.text
    assert pending.json()["status"] == "processed"

    succeeded = client.post(
        "/internal/payment-webhooks/manual_test",
        headers={"X-Internal-Webhook-Secret": "change-me"},
        json=webhook_payload(intent["public_id"], "succeeded", "evt-succeeded"),
    )
    assert succeeded.status_code == 200, succeeded.text
    assert succeeded.json()["status"] == "processed"

    after = wallet_snapshot(client, user_token)
    assert after == before

    db = SessionLocal()
    try:
        entity = db.scalar(select(PaymentIntent).where(PaymentIntent.public_id == intent["public_id"]))
        assert entity.status == "succeeded"
        assert entity.succeeded_at is not None
        assert db.scalar(select(func.count(WalletTransaction.id)).where(WalletTransaction.user_id == 2)) == 0
    finally:
        db.close()


def test_payment_webhook_duplicate_event_does_not_process_twice(client, user_token):
    intent = create_payment_intent(client, user_token)
    payload = webhook_payload(intent["public_id"], "pending", "evt-duplicate")
    headers = {"X-Internal-Webhook-Secret": "change-me", "Idempotency-Key": "webhook-1"}

    first = client.post("/internal/payment-webhooks/manual_test", headers=headers, json=payload)
    second = client.post("/internal/payment-webhooks/manual_test", headers=headers, json=payload)

    assert first.status_code == 200, first.text
    assert first.json()["status"] == "processed"
    assert second.status_code == 200, second.text
    assert second.json()["status"] == "duplicate"

    db = SessionLocal()
    try:
        assert db.scalar(select(func.count(PaymentWebhookEvent.id))) == 1
    finally:
        db.close()


def test_payment_webhook_invalid_transition_ignored(client, user_token):
    intent = create_payment_intent(client, user_token)
    failed = client.post(
        "/internal/payment-webhooks/manual_test",
        headers={"X-Internal-Webhook-Secret": "change-me"},
        json=webhook_payload(intent["public_id"], "failed", "evt-failed"),
    )
    assert failed.status_code == 200, failed.text
    assert failed.json()["status"] == "processed"

    succeeded = client.post(
        "/internal/payment-webhooks/manual_test",
        headers={"X-Internal-Webhook-Secret": "change-me"},
        json=webhook_payload(intent["public_id"], "succeeded", "evt-succeeded-after-failed"),
    )
    assert succeeded.status_code == 200, succeeded.text
    assert succeeded.json()["status"] == "ignored"

    db = SessionLocal()
    try:
        entity = db.scalar(select(PaymentIntent).where(PaymentIntent.public_id == intent["public_id"]))
        assert entity.status == "failed"
        assert entity.succeeded_at is None
    finally:
        db.close()


def test_repeated_succeeded_event_does_not_double_process(client, user_token):
    intent = create_payment_intent(client, user_token)
    client.post(
        "/internal/payment-webhooks/manual_test",
        headers={"X-Internal-Webhook-Secret": "change-me"},
        json=webhook_payload(intent["public_id"], "pending", "evt-pending-repeat"),
    )
    payload = webhook_payload(intent["public_id"], "succeeded", "evt-succeeded-repeat")
    first = client.post(
        "/internal/payment-webhooks/manual_test",
        headers={"X-Internal-Webhook-Secret": "change-me"},
        json=payload,
    )
    second = client.post(
        "/internal/payment-webhooks/manual_test",
        headers={"X-Internal-Webhook-Secret": "change-me"},
        json=payload,
    )
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "processed"
    assert second.status_code == 200, second.text
    assert second.json()["status"] == "duplicate"


def test_payment_webhook_unsupported_provider_rejected(client):
    response = client.post(
        "/internal/payment-webhooks/unknown",
        headers={"X-Internal-Webhook-Secret": "change-me"},
        json={"event_id": "evt-unknown", "status": "pending"},
    )
    assert response.status_code == 400

