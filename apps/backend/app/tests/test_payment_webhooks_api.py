from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import PaymentIntent, PaymentWebhookEvent, Wallet, WalletTransaction


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
    assert "last_webhook_at" in detail.json()
    assert "last_webhook_event_id" in detail.json()
    assert "last_webhook_status" in detail.json()
    assert "last_webhook_error" in detail.json()
    assert "failed_reason" in detail.json()


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


def test_payment_credit_reconciliation_admin_only(client, user_token):
    response = client.get("/admin/payment-intents/reconciliation", headers={"Authorization": f"Bearer {user_token}"})
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


def _balance_amount(snapshot: dict) -> Decimal:
    return Decimal(str(snapshot["balance"]))


def test_payment_webhook_succeeded_transition_credits_wallet_once(client, admin_token, user_token):
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
    assert _balance_amount(after) == _balance_amount(before) + Decimal("10.0000")
    assert after["held_balance"] == before["held_balance"]

    db = SessionLocal()
    try:
        entity = db.scalar(select(PaymentIntent).where(PaymentIntent.public_id == intent["public_id"]))
        assert entity.status == "succeeded"
        assert entity.succeeded_at is not None
        assert entity.last_webhook_at is not None
        assert entity.last_webhook_event_id == "evt-succeeded"
        assert entity.last_webhook_status == "succeeded"
        assert entity.last_webhook_error is None
        tx = db.scalar(
            select(WalletTransaction).where(
                WalletTransaction.payment_intent_id == entity.id,
                WalletTransaction.type == "deposit",
                WalletTransaction.user_id == entity.user_id,
            )
        )
        assert tx is not None
        assert tx.amount == Decimal("10.0000")
        assert tx.reference == f"payment_intent:{entity.public_id}"
        assert tx.tx_metadata["payment_intent_public_id"] == entity.public_id
        assert tx.tx_metadata["provider"] == "manual_test"
    finally:
        db.close()

    reconciliation = client.get(
        "/admin/payment-intents/reconciliation",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert reconciliation.status_code == 200, reconciliation.text
    assert reconciliation.json()["counts"]["succeeded_missing_credit"] == 0
    assert reconciliation.json()["counts"]["credit_non_succeeded"] == 0

    detail = client.get(f"/admin/payment-intents/{entity.id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert detail.status_code == 200, detail.text
    assert detail.json()["last_webhook_at"] is not None
    assert detail.json()["last_webhook_event_id"] == "evt-succeeded"
    assert detail.json()["last_webhook_status"] == "succeeded"
    assert detail.json()["last_webhook_error"] is None

    buyer_detail = client.get(f"/api/v1/payment-intents/{intent['public_id']}", headers={"Authorization": f"Bearer {user_token}"})
    assert buyer_detail.status_code == 200, buyer_detail.text
    assert "last_webhook_at" not in buyer_detail.json()
    assert "last_webhook_event_id" not in buyer_detail.json()
    assert "last_webhook_error" not in buyer_detail.json()


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
        entity = db.scalar(select(PaymentIntent).where(PaymentIntent.public_id == intent["public_id"]))
        assert entity.last_webhook_event_id == "evt-duplicate"
        assert entity.last_webhook_status == "pending"
        assert entity.last_webhook_error == "Duplicate payment webhook event"
    finally:
        db.close()


def test_payment_credit_reconciliation_reports_succeeded_without_wallet_transaction(client, admin_token, user_token):
    intent = create_payment_intent(client, user_token)
    db = SessionLocal()
    try:
        entity = db.scalar(select(PaymentIntent).where(PaymentIntent.public_id == intent["public_id"]))
        entity.status = "succeeded"
        db.commit()
    finally:
        db.close()

    response = client.get("/admin/payment-intents/reconciliation", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["counts"]["succeeded_missing_credit"] == 1
    issue = body["issues"][0]
    assert issue["issue_type"] == "succeeded_missing_credit"
    assert issue["payment_intent_public_id"] == intent["public_id"]
    assert issue["wallet_transaction_id"] is None


def test_payment_credit_reconciliation_reports_credit_for_non_succeeded_intent(client, admin_token, user_token):
    intent = create_payment_intent(client, user_token)
    db = SessionLocal()
    try:
        entity = db.scalar(select(PaymentIntent).where(PaymentIntent.public_id == intent["public_id"]))
        db.add(
            WalletTransaction(
                user_id=entity.user_id,
                payment_intent_id=entity.id,
                type="deposit",
                amount=entity.amount,
                reference=f"payment_intent:{entity.public_id}",
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.get("/admin/payment-intents/reconciliation", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["counts"]["credit_non_succeeded"] == 1
    issue = body["issues"][0]
    assert issue["issue_type"] == "credit_non_succeeded"
    assert issue["payment_intent_public_id"] == intent["public_id"]
    assert issue["wallet_transaction_id"] is not None


def test_payment_webhook_invalid_transition_ignored(client, user_token):
    intent = create_payment_intent(client, user_token)
    before = wallet_snapshot(client, user_token)
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
        assert entity.last_webhook_event_id == "evt-succeeded-after-failed"
        assert entity.last_webhook_status == "succeeded"
        assert entity.last_webhook_error == "Invalid payment intent status transition"
        assert entity.failed_reason is None
        assert db.scalar(
            select(func.count(WalletTransaction.id)).where(WalletTransaction.payment_intent_id == entity.id)
        ) == 0
    finally:
        db.close()
    assert wallet_snapshot(client, user_token) == before


def test_repeated_succeeded_event_does_not_double_process(client, user_token):
    intent = create_payment_intent(client, user_token)
    before = wallet_snapshot(client, user_token)
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

    after = wallet_snapshot(client, user_token)
    assert _balance_amount(after) == _balance_amount(before) + Decimal("10.0000")

    db = SessionLocal()
    try:
        entity = db.scalar(select(PaymentIntent).where(PaymentIntent.public_id == intent["public_id"]))
        assert db.scalar(
            select(func.count(WalletTransaction.id)).where(WalletTransaction.payment_intent_id == entity.id)
        ) == 1
    finally:
        db.close()


def test_different_succeeded_event_for_succeeded_intent_does_not_double_credit(client, user_token):
    intent = create_payment_intent(client, user_token)
    before = wallet_snapshot(client, user_token)
    client.post(
        "/internal/payment-webhooks/manual_test",
        headers={"X-Internal-Webhook-Secret": "change-me"},
        json=webhook_payload(intent["public_id"], "pending", "evt-alt-pending"),
    )
    first = client.post(
        "/internal/payment-webhooks/manual_test",
        headers={"X-Internal-Webhook-Secret": "change-me"},
        json=webhook_payload(intent["public_id"], "succeeded", "evt-alt-succeeded-1"),
    )
    second = client.post(
        "/internal/payment-webhooks/manual_test",
        headers={"X-Internal-Webhook-Secret": "change-me"},
        json=webhook_payload(intent["public_id"], "succeeded", "evt-alt-succeeded-2"),
    )

    assert first.status_code == 200, first.text
    assert first.json()["status"] == "processed"
    assert second.status_code == 200, second.text
    assert second.json()["status"] == "ignored"
    assert _balance_amount(wallet_snapshot(client, user_token)) == _balance_amount(before) + Decimal("10.0000")

    db = SessionLocal()
    try:
        entity = db.scalar(select(PaymentIntent).where(PaymentIntent.public_id == intent["public_id"]))
        assert db.scalar(
            select(func.count(WalletTransaction.id)).where(WalletTransaction.payment_intent_id == entity.id)
        ) == 1
    finally:
        db.close()


def test_failed_and_cancelled_webhooks_do_not_credit_wallet(client, user_token):
    failed_intent = create_payment_intent(client, user_token, amount="4.0000")
    cancelled_intent = create_payment_intent(client, user_token, amount="5.0000")
    before = wallet_snapshot(client, user_token)

    failed = client.post(
        "/internal/payment-webhooks/manual_test",
        headers={"X-Internal-Webhook-Secret": "change-me"},
        json={
            **webhook_payload(failed_intent["public_id"], "failed", "evt-no-credit-failed"),
            "failed_reason": "card_declined:test-details",
        },
    )
    cancelled = client.post(
        "/internal/payment-webhooks/manual_test",
        headers={"X-Internal-Webhook-Secret": "change-me"},
        json=webhook_payload(cancelled_intent["public_id"], "cancelled", "evt-no-credit-cancelled"),
    )
    assert failed.status_code == 200, failed.text
    assert cancelled.status_code == 200, cancelled.text
    assert wallet_snapshot(client, user_token) == before

    db = SessionLocal()
    try:
        entity = db.scalar(select(PaymentIntent).where(PaymentIntent.public_id == failed_intent["public_id"]))
        assert entity.status == "failed"
        assert entity.failed_reason == "card_declined:test-details"
        assert entity.last_webhook_status == "failed"
        assert entity.last_webhook_error is None
    finally:
        db.close()


def test_buyer_wallet_transaction_history_includes_payment_intent_deposit(client, user_token):
    intent = create_payment_intent(client, user_token, amount="6.0000")
    client.post(
        "/internal/payment-webhooks/manual_test",
        headers={"X-Internal-Webhook-Secret": "change-me"},
        json=webhook_payload(intent["public_id"], "pending", "evt-history-pending"),
    )
    succeeded = client.post(
        "/internal/payment-webhooks/manual_test",
        headers={"X-Internal-Webhook-Secret": "change-me"},
        json=webhook_payload(intent["public_id"], "succeeded", "evt-history-succeeded"),
    )
    assert succeeded.status_code == 200, succeeded.text

    history = client.get("/api/v1/wallet/transactions", headers={"Authorization": f"Bearer {user_token}"})
    assert history.status_code == 200, history.text
    deposit_rows = [
        row for row in history.json()
        if row["type"] == "deposit" and row["reference"] == f"payment_intent:{intent['public_id']}"
    ]
    assert len(deposit_rows) == 1
    assert deposit_rows[0]["amount"] == "6.0000"
    assert deposit_rows[0]["order_public_id"] is None
    assert "metadata" not in deposit_rows[0]


def test_payment_intent_not_marked_succeeded_if_wallet_credit_fails(client, user_token, monkeypatch):
    intent = create_payment_intent(client, user_token)
    pending = client.post(
        "/internal/payment-webhooks/manual_test",
        headers={"X-Internal-Webhook-Secret": "change-me"},
        json=webhook_payload(intent["public_id"], "pending", "evt-credit-fail-pending"),
    )
    assert pending.status_code == 200, pending.text

    def fail_credit(*args, **kwargs):
        raise RuntimeError("credit failed")

    monkeypatch.setattr("app.services.payment_intents.wallet.deposit_payment_intent", fail_credit)
    with pytest.raises(RuntimeError, match="credit failed"):
        client.post(
            "/internal/payment-webhooks/manual_test",
            headers={"X-Internal-Webhook-Secret": "change-me"},
            json=webhook_payload(intent["public_id"], "succeeded", "evt-credit-fail-succeeded"),
        )

    db = SessionLocal()
    try:
        entity = db.scalar(select(PaymentIntent).where(PaymentIntent.public_id == intent["public_id"]))
        wallet = db.scalar(select(Wallet).where(Wallet.user_id == entity.user_id))
        assert entity.status == "pending"
        assert entity.succeeded_at is None
        assert wallet.balance == Decimal("25.0000")
        assert db.scalar(
            select(func.count(WalletTransaction.id)).where(WalletTransaction.payment_intent_id == entity.id)
        ) == 0
    finally:
        db.close()


def test_payment_webhook_unsupported_provider_rejected(client):
    response = client.post(
        "/internal/payment-webhooks/unknown",
        headers={"X-Internal-Webhook-Secret": "change-me"},
        json={"event_id": "evt-unknown", "status": "pending"},
    )
    assert response.status_code == 400
