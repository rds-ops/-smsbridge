from __future__ import annotations

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import WalletTransaction


def create_order(client, token: str) -> dict:
    response = client.post(
        "/api/v1/orders",
        headers={"Authorization": f"Bearer {token}"},
        json={"service_code": "telegram", "country_iso2": "ID"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def cancel_order(client, token: str, public_id: str) -> dict:
    response = client.post(
        f"/api/v1/orders/{public_id}/cancel",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def count_wallet_transactions(user_id: int) -> int:
    db = SessionLocal()
    try:
        return int(db.scalar(select(func.count(WalletTransaction.id)).where(WalletTransaction.user_id == user_id)) or 0)
    finally:
        db.close()


def test_wallet_transactions_returns_only_safe_fields(client, user_token):
    order = create_order(client, user_token)
    cancel_order(client, user_token, order["public_id"])

    response = client.get("/api/v1/wallet/transactions", headers={"Authorization": f"Bearer {user_token}"})
    assert response.status_code == 200, response.text
    rows = response.json()
    assert len(rows) == 2

    for row in rows:
        assert "id" in row
        assert "type" in row
        assert "amount" in row
        assert "status" in row
        assert "created_at" in row
        assert "order_id" not in row
        assert "user_id" not in row
        assert "metadata" not in row
        assert "tx_metadata" not in row

    assert {r["type"] for r in rows} == {"hold", "refund"}
    assert all(r["order_public_id"] == order["public_id"] for r in rows)


def test_wallet_transactions_pagination(client, user_token):
    for _ in range(3):
        order = create_order(client, user_token)
        cancel_order(client, user_token, order["public_id"])

    response_1 = client.get(
        "/api/v1/wallet/transactions?limit=2&offset=0",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response_1.status_code == 200, response_1.text
    assert len(response_1.json()) == 2

    response_2 = client.get(
        "/api/v1/wallet/transactions?limit=2&offset=2",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response_2.status_code == 200, response_2.text
    assert len(response_2.json()) == 2


def test_wallet_transactions_does_not_include_other_users(client, admin_token, user_token):
    my_order = create_order(client, user_token)
    cancel_order(client, user_token, my_order["public_id"])

    register = client.post(
        "/auth/register",
        json={"email": "other-user@example.com", "password": "change-me", "locale": "en"},
    )
    assert register.status_code == 200, register.text
    other_token = register.json()["access_token"]

    other_me = client.get("/auth/me", headers={"Authorization": f"Bearer {other_token}"})
    assert other_me.status_code == 200, other_me.text
    other_user_id = other_me.json()["id"]
    deposit = client.post(
        "/admin/wallets/deposit",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"user_id": other_user_id, "amount": "25.0000", "reference": "test"},
    )
    assert deposit.status_code == 200, deposit.text

    other_order = create_order(client, other_token)
    cancel_order(client, other_token, other_order["public_id"])

    response = client.get("/api/v1/wallet/transactions", headers={"Authorization": f"Bearer {user_token}"})
    assert response.status_code == 200, response.text
    rows = response.json()
    assert all(r.get("order_public_id") != other_order["public_id"] for r in rows)

    # Double-check against DB counts to ensure we're not leaking cross-user rows.
    assert len(rows) == count_wallet_transactions(user_id=2)


def test_wallet_transactions_api_key_auth_works(client, user_token):
    order = create_order(client, user_token)
    cancel_order(client, user_token, order["public_id"])

    regen = client.post("/api/v1/api-key/regenerate", headers={"Authorization": f"Bearer {user_token}"})
    assert regen.status_code == 200, regen.text
    api_key = regen.json()["api_key"]

    response = client.get("/api/v1/wallet/transactions", headers={"Authorization": f"Bearer {api_key}"})
    assert response.status_code == 200, response.text
    assert len(response.json()) == 2


def test_wallet_transactions_order_public_id_is_null_when_no_order(client, admin_token, user_token):
    # Create a non-order transaction for the buyer and ensure it returns with order_public_id=null.
    response = client.post(
        "/admin/wallets/deposit",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"user_id": 2, "amount": "1.0000", "reference": "test-deposit"},
    )
    assert response.status_code == 200, response.text

    txs = client.get("/api/v1/wallet/transactions", headers={"Authorization": f"Bearer {user_token}"}).json()
    deposit_rows = [row for row in txs if row["type"] == "deposit" and row.get("reference") == "test-deposit"]
    assert deposit_rows
    assert deposit_rows[0]["order_public_id"] is None
