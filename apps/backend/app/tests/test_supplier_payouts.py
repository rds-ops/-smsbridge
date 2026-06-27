from __future__ import annotations

from decimal import Decimal

from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.models import AuditLog, Supplier, SupplierPayoutRequest, SupplierTransaction


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


def test_supplier_payout_request_requires_minimum_amount(client, admin_token):
    supplier = create_supplier(client, admin_token)
    api_key = supplier_key(client, admin_token, supplier["id"])
    _fund_supplier(client, admin_token, supplier["id"])

    response = _create_payout(client, api_key, "0.5000")

    assert response.status_code == 400
    assert "Minimum payout amount" in response.json()["detail"]
    with SessionLocal() as db:
        supplier_row = db.get(Supplier, supplier["id"])
        assert supplier_row.balance == Decimal("10.0000")
        assert supplier_row.held_balance == Decimal("0.0000")
        assert db.scalar(select(SupplierTransaction).where(SupplierTransaction.type == "payout_hold")) is None


def test_supplier_payout_request_requires_method_and_address(client, admin_token):
    supplier = create_supplier(client, admin_token)
    api_key = supplier_key(client, admin_token, supplier["id"])
    _fund_supplier(client, admin_token, supplier["id"])

    missing_method = client.post(
        "/supplier/v1/payout-requests",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"amount": "4.0000", "payout_address": "test-address"},
    )
    missing_address = client.post(
        "/supplier/v1/payout-requests",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"amount": "4.0000", "payout_method": "manual_test"},
    )

    assert missing_method.status_code == 400
    assert missing_method.json()["detail"] == "Payout method is required"
    assert missing_address.status_code == 400
    assert missing_address.json()["detail"] == "Payout address is required"
    with SessionLocal() as db:
        supplier_row = db.get(Supplier, supplier["id"])
        assert supplier_row.balance == Decimal("10.0000")
        assert supplier_row.held_balance == Decimal("0.0000")
        assert db.scalar(select(SupplierPayoutRequest).where(SupplierPayoutRequest.supplier_id == supplier["id"])) is None


def test_blocked_supplier_cannot_create_payout_request(client, admin_token):
    supplier = create_supplier(client, admin_token, status="blocked")
    api_key = supplier_key(client, admin_token, supplier["id"])
    _fund_supplier(client, admin_token, supplier["id"])

    response = _create_payout(client, api_key, "4.0000")

    assert response.status_code == 403
    with SessionLocal() as db:
        supplier_row = db.get(Supplier, supplier["id"])
        assert supplier_row.balance == Decimal("10.0000")
        assert supplier_row.held_balance == Decimal("0.0000")


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


def test_supplier_can_list_own_transactions_with_safe_fields(client, admin_token):
    supplier = create_supplier(client, admin_token)
    api_key = supplier_key(client, admin_token, supplier["id"])
    _fund_supplier(client, admin_token, supplier["id"])

    response = client.get("/supplier/v1/transactions", headers={"Authorization": f"Bearer {api_key}"})

    assert response.status_code == 200, response.text
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["type"] == "adjustment"
    assert rows[0]["amount"] == "10.0000"
    assert rows[0]["currency"] == "USD"
    assert rows[0]["status"] == "completed"
    assert rows[0]["reference"] == "test-fund"
    assert "supplier_id" not in rows[0]
    assert "activation_id" not in rows[0]
    assert "order_id" not in rows[0]
    assert "tx_metadata" not in rows[0]


def test_supplier_transactions_are_supplier_scoped(client, admin_token):
    first = create_supplier(client, admin_token)
    second = create_supplier(client, admin_token)
    first_key = supplier_key(client, admin_token, first["id"])
    _fund_supplier(client, admin_token, first["id"], "7.0000")
    _fund_supplier(client, admin_token, second["id"], "9.0000")

    response = client.get("/supplier/v1/transactions", headers={"Authorization": f"Bearer {first_key}"})

    assert response.status_code == 200, response.text
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["amount"] == "7.0000"
    assert "9.0000" not in str(rows)


def test_supplier_transactions_require_supplier_auth(client, user_token):
    missing = client.get("/supplier/v1/transactions")
    buyer = client.get("/supplier/v1/transactions", headers={"Authorization": f"Bearer {user_token}"})

    assert missing.status_code == 401
    assert buyer.status_code == 401


def test_blocked_supplier_can_read_own_transactions_like_other_read_endpoints(client, admin_token):
    supplier = create_supplier(client, admin_token, status="blocked")
    api_key = supplier_key(client, admin_token, supplier["id"])
    _fund_supplier(client, admin_token, supplier["id"])

    response = client.get("/supplier/v1/transactions", headers={"Authorization": f"Bearer {api_key}"})

    assert response.status_code == 200, response.text
    assert response.json()[0]["type"] == "adjustment"


def test_supplier_transactions_limit_offset_and_filters(client, admin_token):
    supplier = create_supplier(client, admin_token)
    api_key = supplier_key(client, admin_token, supplier["id"])
    _fund_supplier(client, admin_token, supplier["id"], "10.0000")
    first_payout = _create_payout(client, api_key, "1.0000")
    second_payout = _create_payout(client, api_key, "2.0000")
    assert first_payout.status_code == 200, first_payout.text
    assert second_payout.status_code == 200, second_payout.text

    filtered = client.get(
        "/supplier/v1/transactions?type=payout_hold&status=completed",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    first_page = client.get(
        "/supplier/v1/transactions?limit=1&offset=0",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    second_page = client.get(
        "/supplier/v1/transactions?limit=1&offset=1",
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert filtered.status_code == 200, filtered.text
    assert [row["type"] for row in filtered.json()] == ["payout_hold", "payout_hold"]
    assert first_page.status_code == 200, first_page.text
    assert second_page.status_code == 200, second_page.text
    assert len(first_page.json()) == 1
    assert len(second_page.json()) == 1
    assert first_page.json()[0] != second_page.json()[0]


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


def test_admin_payout_actions_are_audit_logged(client, admin_token):
    first_supplier = create_supplier(client, admin_token)
    first_key = supplier_key(client, admin_token, first_supplier["id"])
    _fund_supplier(client, admin_token, first_supplier["id"])
    approved_payout = _create_payout(client, first_key, "4.0000").json()

    second_supplier = create_supplier(client, admin_token)
    second_key = supplier_key(client, admin_token, second_supplier["id"])
    _fund_supplier(client, admin_token, second_supplier["id"])
    rejected_payout = _create_payout(client, second_key, "4.0000").json()

    third_supplier = create_supplier(client, admin_token)
    third_key = supplier_key(client, admin_token, third_supplier["id"])
    _fund_supplier(client, admin_token, third_supplier["id"])
    paid_payout = _create_payout(client, third_key, "4.0000").json()

    assert client.post(
        f"/admin/supplier-payout-requests/{approved_payout['id']}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"admin_note": "approved"},
    ).status_code == 200
    assert client.post(
        f"/admin/supplier-payout-requests/{rejected_payout['id']}/reject",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reason": "bad address"},
    ).status_code == 200
    assert client.post(
        f"/admin/supplier-payout-requests/{paid_payout['id']}/mark-paid",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"admin_note": "paid"},
    ).status_code == 200

    with SessionLocal() as db:
        actions = set(
            db.scalars(
                select(AuditLog.action).where(
                    AuditLog.entity_type == "supplier_payout",
                    AuditLog.entity_id.in_(
                        [str(approved_payout["id"]), str(rejected_payout["id"]), str(paid_payout["id"])]
                    ),
                )
            )
        )
        assert actions == {"supplier_payout.approve", "supplier_payout.reject", "supplier_payout.mark_paid"}


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


def test_supplier_payout_reconciliation_clean_flow_reports_no_issues(client, admin_token):
    supplier = create_supplier(client, admin_token)
    api_key = supplier_key(client, admin_token, supplier["id"])
    _fund_supplier(client, admin_token, supplier["id"])
    _create_payout(client, api_key, "4.0000")

    response = client.get(
        "/admin/supplier-payout-requests/reconciliation",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["counts"]["missing_payout_hold"] == 0
    assert body["counts"]["missing_payout_release"] == 0
    assert body["counts"]["missing_payout_paid"] == 0
    assert body["counts"]["duplicate_payout_transaction"] == 0
    assert body["counts"]["supplier_held_balance_mismatch"] == 0
    assert body["issues"] == []


def test_supplier_payout_reconciliation_reports_requested_missing_hold(client, admin_token):
    supplier = create_supplier(client, admin_token)
    api_key = supplier_key(client, admin_token, supplier["id"])
    _fund_supplier(client, admin_token, supplier["id"])
    payout = _create_payout(client, api_key, "4.0000").json()

    with SessionLocal() as db:
        db.execute(
            delete(SupplierTransaction).where(
                SupplierTransaction.reference == f"payout:{payout['public_id']}",
                SupplierTransaction.type == "payout_hold",
            )
        )
        db.commit()

    response = client.get(
        "/admin/supplier-payout-requests/reconciliation",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["counts"]["missing_payout_hold"] == 1
    assert any(issue["issue_type"] == "missing_payout_hold" and issue["payout_id"] == payout["id"] for issue in body["issues"])


def test_supplier_payout_reconciliation_reports_rejected_missing_release(client, admin_token):
    supplier = create_supplier(client, admin_token)
    api_key = supplier_key(client, admin_token, supplier["id"])
    _fund_supplier(client, admin_token, supplier["id"])
    payout = _create_payout(client, api_key, "4.0000").json()
    rejected = client.post(
        f"/admin/supplier-payout-requests/{payout['id']}/reject",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reason": "test"},
    )
    assert rejected.status_code == 200, rejected.text

    with SessionLocal() as db:
        db.execute(
            delete(SupplierTransaction).where(
                SupplierTransaction.reference == f"payout:{payout['public_id']}",
                SupplierTransaction.type == "payout_release",
            )
        )
        db.commit()

    response = client.get(
        "/admin/supplier-payout-requests/reconciliation",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["counts"]["missing_payout_release"] == 1
    assert any(issue["issue_type"] == "missing_payout_release" and issue["payout_id"] == payout["id"] for issue in body["issues"])


def test_supplier_payout_reconciliation_reports_paid_missing_paid_transaction(client, admin_token):
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

    with SessionLocal() as db:
        db.execute(
            delete(SupplierTransaction).where(
                SupplierTransaction.reference == f"payout:{payout['public_id']}",
                SupplierTransaction.type == "payout_paid",
            )
        )
        db.commit()

    response = client.get(
        "/admin/supplier-payout-requests/reconciliation",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["counts"]["missing_payout_paid"] == 1
    assert any(issue["issue_type"] == "missing_payout_paid" and issue["payout_id"] == payout["id"] for issue in body["issues"])


def test_supplier_payout_reconciliation_endpoint_is_admin_only(client, user_token):
    response = client.get(
        "/admin/supplier-payout-requests/reconciliation",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403
