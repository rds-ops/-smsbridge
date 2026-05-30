from __future__ import annotations

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Provider


def test_internal_provider_webhook_missing_secret_is_rejected(client):
    response = client.post("/internal/provider-webhooks/mock", json={"event": "sms"})
    assert response.status_code in {401, 403}


def test_internal_provider_webhook_invalid_secret_is_rejected(client):
    response = client.post(
        "/internal/provider-webhooks/mock",
        headers={"X-Internal-Webhook-Secret": "wrong-secret"},
        json={"event": "sms"},
    )
    assert response.status_code in {401, 403}


def test_internal_provider_webhook_unknown_provider_returns_clean_error(client):
    response = client.post(
        "/internal/provider-webhooks/does_not_exist",
        headers={"X-Internal-Webhook-Secret": "change-me"},
        json={"event": "sms"},
    )
    assert response.status_code == 404


def test_internal_provider_webhook_inactive_provider_returns_clean_error(client):
    db = SessionLocal()
    try:
        provider = db.scalar(select(Provider).where(Provider.code == "mock"))
        provider.status = "inactive"
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/internal/provider-webhooks/mock",
        headers={"X-Internal-Webhook-Secret": "change-me"},
        json={"event": "sms"},
    )
    assert response.status_code == 409


def test_internal_provider_webhook_active_provider_returns_accepted(client):
    response = client.post(
        "/internal/provider-webhooks/mock",
        headers={"X-Internal-Webhook-Secret": "change-me"},
        json={"event": "sms"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "accepted"
    assert body["provider_code"] == "mock"

