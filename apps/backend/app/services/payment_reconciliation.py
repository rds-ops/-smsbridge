from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import PaymentIntent, WalletTransaction


SUCCEEDED_MISSING_CREDIT = "succeeded_missing_credit"
CREDIT_NON_SUCCEEDED = "credit_non_succeeded"
DUPLICATE_CREDIT = "duplicate_credit"


@dataclass(frozen=True)
class PaymentCreditIssue:
    issue_type: str
    payment_intent_id: int | None
    payment_intent_public_id: str | None
    user_id: int | None
    provider: str | None
    amount: Decimal | None
    status: str | None
    wallet_transaction_id: int | None
    created_at: datetime | None


@dataclass(frozen=True)
class PaymentCreditReconciliation:
    counts: dict[str, int]
    issues: list[PaymentCreditIssue]


def reconcile_payment_credits(db: Session, *, limit: int = 100) -> PaymentCreditReconciliation:
    capped_limit = max(1, min(limit, 500))
    counts = {
        SUCCEEDED_MISSING_CREDIT: _count_succeeded_missing_credit(db),
        CREDIT_NON_SUCCEEDED: _count_credit_non_succeeded(db),
        DUPLICATE_CREDIT: _count_duplicate_credit_intents(db),
    }

    issues: list[PaymentCreditIssue] = []
    remaining = capped_limit
    for issue in _succeeded_missing_credit_issues(db, remaining):
        issues.append(issue)
    remaining = capped_limit - len(issues)
    if remaining > 0:
        for issue in _credit_non_succeeded_issues(db, remaining):
            issues.append(issue)
    remaining = capped_limit - len(issues)
    if remaining > 0:
        for issue in _duplicate_credit_issues(db, remaining):
            issues.append(issue)

    return PaymentCreditReconciliation(counts=counts, issues=issues)


def _deposit_exists():
    return (
        select(WalletTransaction.id)
        .where(
            WalletTransaction.payment_intent_id == PaymentIntent.id,
            WalletTransaction.type == "deposit",
            WalletTransaction.status == "completed",
        )
        .exists()
    )


def _count_succeeded_missing_credit(db: Session) -> int:
    return int(
        db.scalar(
            select(func.count(PaymentIntent.id)).where(
                PaymentIntent.status == "succeeded",
                ~_deposit_exists(),
            )
        )
        or 0
    )


def _count_credit_non_succeeded(db: Session) -> int:
    return int(
        db.scalar(
            select(func.count(WalletTransaction.id))
            .join(PaymentIntent, PaymentIntent.id == WalletTransaction.payment_intent_id)
            .where(
                WalletTransaction.payment_intent_id.is_not(None),
                PaymentIntent.status != "succeeded",
            )
        )
        or 0
    )


def _count_duplicate_credit_intents(db: Session) -> int:
    rows = db.execute(
        select(WalletTransaction.payment_intent_id)
        .where(WalletTransaction.payment_intent_id.is_not(None))
        .group_by(WalletTransaction.payment_intent_id)
        .having(func.count(WalletTransaction.id) > 1)
    ).all()
    return len(rows)


def _succeeded_missing_credit_issues(db: Session, limit: int) -> list[PaymentCreditIssue]:
    intents = db.scalars(
        select(PaymentIntent)
        .where(PaymentIntent.status == "succeeded", ~_deposit_exists())
        .order_by(PaymentIntent.updated_at.desc(), PaymentIntent.id.desc())
        .limit(limit)
    )
    return [
        PaymentCreditIssue(
            issue_type=SUCCEEDED_MISSING_CREDIT,
            payment_intent_id=intent.id,
            payment_intent_public_id=intent.public_id,
            user_id=intent.user_id,
            provider=intent.provider,
            amount=intent.amount,
            status=intent.status,
            wallet_transaction_id=None,
            created_at=intent.created_at,
        )
        for intent in intents
    ]


def _credit_non_succeeded_issues(db: Session, limit: int) -> list[PaymentCreditIssue]:
    rows = db.execute(
        select(PaymentIntent, WalletTransaction)
        .join(WalletTransaction, WalletTransaction.payment_intent_id == PaymentIntent.id)
        .where(WalletTransaction.payment_intent_id.is_not(None), PaymentIntent.status != "succeeded")
        .order_by(WalletTransaction.created_at.desc(), WalletTransaction.id.desc())
        .limit(limit)
    ).all()
    return [
        PaymentCreditIssue(
            issue_type=CREDIT_NON_SUCCEEDED,
            payment_intent_id=intent.id,
            payment_intent_public_id=intent.public_id,
            user_id=intent.user_id,
            provider=intent.provider,
            amount=intent.amount,
            status=intent.status,
            wallet_transaction_id=tx.id,
            created_at=tx.created_at,
        )
        for intent, tx in rows
    ]


def _duplicate_credit_issues(db: Session, limit: int) -> list[PaymentCreditIssue]:
    rows = db.execute(
        select(PaymentIntent, func.count(WalletTransaction.id).label("tx_count"))
        .join(WalletTransaction, WalletTransaction.payment_intent_id == PaymentIntent.id)
        .where(WalletTransaction.payment_intent_id.is_not(None))
        .group_by(PaymentIntent.id)
        .having(func.count(WalletTransaction.id) > 1)
        .order_by(PaymentIntent.updated_at.desc(), PaymentIntent.id.desc())
        .limit(limit)
    ).all()
    return [
        PaymentCreditIssue(
            issue_type=DUPLICATE_CREDIT,
            payment_intent_id=intent.id,
            payment_intent_public_id=intent.public_id,
            user_id=intent.user_id,
            provider=intent.provider,
            amount=intent.amount,
            status=intent.status,
            wallet_transaction_id=None,
            created_at=intent.created_at,
        )
        for intent, _tx_count in rows
    ]
