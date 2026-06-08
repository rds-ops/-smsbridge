from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, literal, select
from sqlalchemy.orm import Session

from app.models import Supplier, SupplierPayoutRequest, SupplierTransaction


MISSING_HOLD = "missing_payout_hold"
MISSING_RELEASE = "missing_payout_release"
MISSING_PAID = "missing_payout_paid"
DUPLICATE_PAYOUT_TRANSACTION = "duplicate_payout_transaction"
SUPPLIER_HELD_BALANCE_MISMATCH = "supplier_held_balance_mismatch"

ACTIVE_PAYOUT_STATUSES = {"requested", "approved"}


@dataclass(frozen=True)
class SupplierPayoutIssue:
    issue_type: str
    payout_id: int | None
    payout_public_id: str | None
    supplier_id: int
    status: str | None
    amount: Decimal | None
    created_at: datetime | None
    updated_at: datetime | None


@dataclass(frozen=True)
class SupplierPayoutReconciliation:
    counts: dict[str, int]
    issues: list[SupplierPayoutIssue]


def reconcile_supplier_payouts(db: Session, *, limit: int = 100) -> SupplierPayoutReconciliation:
    capped_limit = max(1, min(limit, 500))
    counts = {
        MISSING_HOLD: _count_missing_tx(db, {"requested", "approved"}, "payout_hold"),
        MISSING_RELEASE: _count_missing_tx(db, {"rejected", "cancelled"}, "payout_release"),
        MISSING_PAID: _count_missing_tx(db, {"paid"}, "payout_paid"),
        DUPLICATE_PAYOUT_TRANSACTION: _count_duplicate_payout_transactions(db),
        SUPPLIER_HELD_BALANCE_MISMATCH: _count_supplier_held_balance_mismatches(db),
    }

    issues: list[SupplierPayoutIssue] = []
    for loader in (
        lambda remaining: _missing_tx_issues(db, MISSING_HOLD, {"requested", "approved"}, "payout_hold", remaining),
        lambda remaining: _missing_tx_issues(db, MISSING_RELEASE, {"rejected", "cancelled"}, "payout_release", remaining),
        lambda remaining: _missing_tx_issues(db, MISSING_PAID, {"paid"}, "payout_paid", remaining),
        lambda remaining: _duplicate_payout_transaction_issues(db, remaining),
        lambda remaining: _supplier_held_balance_mismatch_issues(db, remaining),
    ):
        remaining = capped_limit - len(issues)
        if remaining <= 0:
            break
        issues.extend(loader(remaining))

    return SupplierPayoutReconciliation(counts=counts, issues=issues)


def _payout_reference_exists(tx_type: str):
    payout_ref = literal("payout:") + SupplierPayoutRequest.public_id
    return (
        select(SupplierTransaction.id)
        .where(
            SupplierTransaction.supplier_id == SupplierPayoutRequest.supplier_id,
            SupplierTransaction.type == tx_type,
            SupplierTransaction.status == "completed",
            SupplierTransaction.reference == payout_ref,
        )
        .exists()
    )


def _count_missing_tx(db: Session, statuses: set[str], tx_type: str) -> int:
    return int(
        db.scalar(
            select(func.count(SupplierPayoutRequest.id)).where(
                SupplierPayoutRequest.status.in_(statuses),
                ~_payout_reference_exists(tx_type),
            )
        )
        or 0
    )


def _missing_tx_issues(
    db: Session,
    issue_type: str,
    statuses: set[str],
    tx_type: str,
    limit: int,
) -> list[SupplierPayoutIssue]:
    payouts = db.scalars(
        select(SupplierPayoutRequest)
        .where(
            SupplierPayoutRequest.status.in_(statuses),
            ~_payout_reference_exists(tx_type),
        )
        .order_by(SupplierPayoutRequest.updated_at.desc(), SupplierPayoutRequest.id.desc())
        .limit(limit)
    )
    return [_issue(issue_type, payout) for payout in payouts]


def _count_duplicate_payout_transactions(db: Session) -> int:
    rows = db.execute(
        select(SupplierTransaction.reference, SupplierTransaction.type)
        .where(
            SupplierTransaction.reference.like("payout:%"),
            SupplierTransaction.type.in_(("payout_hold", "payout_release", "payout_cancel", "payout_paid")),
            SupplierTransaction.status == "completed",
        )
        .group_by(SupplierTransaction.reference, SupplierTransaction.type)
        .having(func.count(SupplierTransaction.id) > 1)
    ).all()
    return len(rows)


def _duplicate_payout_transaction_issues(db: Session, limit: int) -> list[SupplierPayoutIssue]:
    payout_ref = literal("payout:") + SupplierPayoutRequest.public_id
    rows = db.execute(
        select(SupplierPayoutRequest)
        .join(SupplierTransaction, SupplierTransaction.reference == payout_ref)
        .where(
            SupplierTransaction.type.in_(("payout_hold", "payout_release", "payout_cancel", "payout_paid")),
            SupplierTransaction.status == "completed",
        )
        .group_by(SupplierPayoutRequest.id, SupplierTransaction.type)
        .having(func.count(SupplierTransaction.id) > 1)
        .order_by(SupplierPayoutRequest.updated_at.desc(), SupplierPayoutRequest.id.desc())
        .limit(limit)
    ).scalars()
    return [_issue(DUPLICATE_PAYOUT_TRANSACTION, payout) for payout in rows]


def _active_payout_sum_subquery():
    return (
        select(
            SupplierPayoutRequest.supplier_id.label("supplier_id"),
            func.coalesce(func.sum(SupplierPayoutRequest.amount), Decimal("0.0000")).label("active_amount"),
        )
        .where(SupplierPayoutRequest.status.in_(ACTIVE_PAYOUT_STATUSES))
        .group_by(SupplierPayoutRequest.supplier_id)
        .subquery()
    )


def _count_supplier_held_balance_mismatches(db: Session) -> int:
    active_sum = _active_payout_sum_subquery()
    return int(
        db.scalar(
            select(func.count(Supplier.id))
            .outerjoin(active_sum, active_sum.c.supplier_id == Supplier.id)
            .where(Supplier.held_balance != func.coalesce(active_sum.c.active_amount, Decimal("0.0000")))
        )
        or 0
    )


def _supplier_held_balance_mismatch_issues(db: Session, limit: int) -> list[SupplierPayoutIssue]:
    active_sum = _active_payout_sum_subquery()
    rows = db.execute(
        select(Supplier, SupplierPayoutRequest)
        .outerjoin(active_sum, active_sum.c.supplier_id == Supplier.id)
        .outerjoin(SupplierPayoutRequest, SupplierPayoutRequest.supplier_id == Supplier.id)
        .where(Supplier.held_balance != func.coalesce(active_sum.c.active_amount, Decimal("0.0000")))
        .order_by(SupplierPayoutRequest.updated_at.desc().nullslast(), Supplier.id.desc())
        .limit(limit)
    ).all()
    return [
        SupplierPayoutIssue(
            issue_type=SUPPLIER_HELD_BALANCE_MISMATCH,
            payout_id=payout.id if payout else None,
            payout_public_id=payout.public_id if payout else None,
            supplier_id=supplier.id,
            status=payout.status if payout else None,
            amount=payout.amount if payout else None,
            created_at=payout.created_at if payout else None,
            updated_at=payout.updated_at if payout else None,
        )
        for supplier, payout in rows
    ]


def _issue(issue_type: str, payout: SupplierPayoutRequest) -> SupplierPayoutIssue:
    return SupplierPayoutIssue(
        issue_type=issue_type,
        payout_id=payout.id,
        payout_public_id=payout.public_id,
        supplier_id=payout.supplier_id,
        status=payout.status,
        amount=payout.amount,
        created_at=payout.created_at,
        updated_at=payout.updated_at,
    )
