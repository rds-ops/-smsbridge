from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Supplier, SupplierPayoutRequest, SupplierTransaction


def create_supplier(client, admin_token, status: str = "active") -> dict:
    response = client.post(
        "/admin/suppliers",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": "Payout Supplier", "email": "payout-supplier@example.com", "status": status, "reward_percent": "70.00"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def supplier_key(client, admin_token, supplier_id: int) -> str:
    response = client.post(
        f"/admin/suppliers/{supplier_id}/api-key/regenerate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    return response.json()["api_key"]


def _fund_supplier(client, admin_token: str, supplier_id: int, amount: str = "10.0000") -> None:
    response = client.post(
        f"/admin/suppliers/{supplier_id}/adjustment",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"amount": amount, "reference": "test-fund", "metadata": {"reason": "payout-test"}},
    )
    assert response.status_code == 200, response.text


def _create_payout(client, api_key: str, amount: str = "4.0000"):
    return client.post(
        "/supplier/v1/payout-requests",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"amount": amount, "payout_method": "manual_test", "payout_address": "test-address"},
    )


def test_supplier_can_create_payout_request_and_hold_balance(client, admin_token):
    supplier = create_supplier(client, admin_token)
    api_key = supplier_key(client, admin_token, supplier["id"])
    _fund_supplier(client, admin_token, supplier["id"])

    response = _create_payout(client, api_key, "4.0000")
    assert response.status_code == 200, response.text
    payout = response.json()
    assert payout["status"] == "requested"
    assert payout["amount"] == "4.0000"
    assert payout["currency"] == "USD"

    with SessionLocal() as db:
        supplier_row = db.get(Supplier, supplier["id"])
        assert supplier_row.balance == Decimal("6.0000")
        assert supplier_row.held_balance == Decimal("4.0000")
        tx = db.scalar(
            select(SupplierTransaction).where(
                SupplierTransaction.supplier_id == supplier["id"],
                SupplierTransaction.type == "payout_hold",
                SupplierTransaction.reference == f"payout:{payout['public_id']}",
            )
        )
        assert tx is not None
        assert tx.amount == Decimal("4.0000")


def test_supplier_payout_request_rejects_insufficient_balance(client, admin_token):
    supplier = create_supplier(client, admin_token)
    api_key = supplier_key(client, admin_token, supplier["id"])

    response = _create_payout(client, api_key, "1.0000")
    assert response.status_code == 400
    assert response.json()["detail"] == "Insufficient supplier balance"


def test_supplier_sees_only_own_payout_requests(client, admin_token):
    first = create_supplier(client, admin_token)
    second = create_supplier(client, admin_token)
    first_key = supplier_key(client, admin_token, first["id"])
    second_key = supplier_key(client, admin_token, second["id"])
    _fund_supplier(client, admin_token, first["id"])
    _fund_supplier(client, admin_token, second["id"])
    first_payout = _create_payout(client, first_key, "2.0000").json()
    _create_payout(client, second_key, "3.0000")

    response = client.get("/supplier/v1/payout-requests", headers={"Authorization": f"Bearer {first_key}"})
    assert response.status_code == 200, response.text
    rows = response.json()
    assert [row["public_id"] for row in rows] == [first_payout["public_id"]]


def test_admin_can_list_detail_and_approve_supplier_payout(client, admin_token):
    supplier = create_supplier(client, admin_token)
    api_key = supplier_key(client, admin_token, supplier["id"])
    _fund_supplier(client, admin_token, supplier["id"])
    payout = _create_payout(client, api_key, "4.0000").json()

    listed = client.get(
        "/admin/supplier-payout-requests",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"status": "requested", "supplier_id": supplier["id"]},
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()[0]["id"] == payout["id"]

    detail = client.get(f"/admin/supplier-payout-requests/{payout['id']}", headers={"Authorization": f"Bearer {admin_token}"})
    assert detail.status_code == 200, detail.text
    assert detail.json()["public_id"] == payout["public_id"]

    approved = client.post(
        f"/admin/supplier-payout-requests/{payout['id']}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"admin_note": "approved for manual payout"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"


def test_admin_reject_releases_held_funds_once(client, admin_token):
    supplier = create_supplier(client, admin_token)
    api_key = supplier_key(client, admin_token, supplier["id"])
    _fund_supplier(client, admin_token, supplier["id"])
    payout = _create_payout(client, api_key, "4.0000").json()

    first = client.post(
        f"/admin/supplier-payout-requests/{payout['id']}/reject",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reason": "invalid address"},
    )
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "rejected"

    second = client.post(
        f"/admin/supplier-payout-requests/{payout['id']}/reject",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reason": "invalid address"},
    )
    assert second.status_code == 200, second.text
    assert second.json()["status"] == "rejected"

    with SessionLocal() as db:
        supplier_row = db.get(Supplier, supplier["id"])
        assert supplier_row.balance == Decimal("10.0000")
        assert supplier_row.held_balance == Decimal("0.0000")
        release_txs = list(
            db.scalars(
                select(SupplierTransaction).where(
                    SupplierTransaction.supplier_id == supplier["id"],
                    SupplierTransaction.type == "payout_release",
                )
            )
        )
        assert len(release_txs) == 1


def test_admin_mark_paid_decreases_held_balance_once(client, admin_token):
    supplier = create_supplier(client, admin_token)
    api_key = supplier_key(client, admin_token, supplier["id"])
    _fund_supplier(client, admin_token, supplier["id"])
    payout = _create_payout(client, api_key, "4.0000").json()

    first = client.post(
        f"/admin/supplier-payout-requests/{payout['id']}/mark-paid",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"admin_note": "paid manually"},
    )
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "paid"

    second = client.post(
        f"/admin/supplier-payout-requests/{payout['id']}/mark-paid",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"admin_note": "paid manually"},
    )
    assert second.status_code == 200, second.text
    assert second.json()["status"] == "paid"

    with SessionLocal() as db:
        supplier_row = db.get(Supplier, supplier["id"])
        assert supplier_row.balance == Decimal("6.0000")
        assert supplier_row.held_balance == Decimal("0.0000")
        paid_txs = list(
            db.scalars(
                select(SupplierTransaction).where(
                    SupplierTransaction.supplier_id == supplier["id"],
                    SupplierTransaction.type == "payout_paid",
                )
            )
        )
        assert len(paid_txs) == 1


def test_non_admin_blocked_from_supplier_payout_admin_endpoints(client, admin_token, user_token):
    supplier = create_supplier(client, admin_token)
    api_key = supplier_key(client, admin_token, supplier["id"])
    _fund_supplier(client, admin_token, supplier["id"])
    payout = _create_payout(client, api_key, "4.0000").json()

    response = client.get(
        f"/admin/supplier-payout-requests/{payout['id']}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403


def test_buyer_cannot_access_supplier_payout_endpoints(client, user_token):
    response = client.get("/supplier/v1/payout-requests", headers={"Authorization": f"Bearer {user_token}"})
    assert response.status_code == 401


def test_paid_payout_cannot_be_rejected_or_double_mutated(client, admin_token):
    supplier = create_supplier(client, admin_token)
    api_key = supplier_key(client, admin_token, supplier["id"])
    _fund_supplier(client, admin_token, supplier["id"])
    payout = _create_payout(client, api_key, "4.0000").json()

    paid = client.post(
        f"/admin/supplier-payout-requests/{payout['id']}/mark-paid",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={},
    )
    assert paid.status_code == 200, paid.text
    rejected = client.post(
        f"/admin/supplier-payout-requests/{payout['id']}/reject",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reason": "too late"},
    )
    assert rejected.status_code == 409

    with SessionLocal() as db:
        payout_row = db.get(SupplierPayoutRequest, payout["id"])
        supplier_row = db.get(Supplier, supplier["id"])
        assert payout_row.status == "paid"
        assert supplier_row.balance == Decimal("6.0000")
        assert supplier_row.held_balance == Decimal("0.0000")
