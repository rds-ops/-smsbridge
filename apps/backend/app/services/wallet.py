from __future__ import annotations
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PaymentIntent, Wallet, WalletTransaction
from app.core.errors import api_error


def _wallet_for_update(db: Session, user_id: int) -> Wallet:
    stmt = select(Wallet).where(Wallet.user_id == user_id).with_for_update()
    wallet = db.scalar(stmt)
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return wallet


def _completed_order_tx(db: Session, order_id: int, tx_type: str) -> WalletTransaction | None:
    return db.scalar(
        select(WalletTransaction).where(
            WalletTransaction.order_id == order_id,
            WalletTransaction.type == tx_type,
            WalletTransaction.status == "completed",
        )
    )


def deposit(db: Session, user_id: int, amount: Decimal, reference: str | None = None) -> Wallet:
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Deposit amount must be positive")
    wallet = _wallet_for_update(db, user_id)
    wallet.balance += amount
    db.add(WalletTransaction(user_id=user_id, type="deposit", amount=amount, reference=reference))
    return wallet


def deposit_payment_intent(db: Session, intent: PaymentIntent) -> Wallet:
    if intent.amount <= 0:
        raise HTTPException(status_code=400, detail="Deposit amount must be positive")

    wallet = _wallet_for_update(db, intent.user_id)
    existing = db.scalar(
        select(WalletTransaction).where(
            WalletTransaction.payment_intent_id == intent.id,
            WalletTransaction.type == "deposit",
            WalletTransaction.status == "completed",
        )
    )
    if existing:
        return wallet

    wallet.balance += intent.amount
    reference = intent.provider_reference or f"payment_intent:{intent.public_id}"
    db.add(
        WalletTransaction(
            user_id=intent.user_id,
            payment_intent_id=intent.id,
            type="deposit",
            amount=intent.amount,
            reference=reference,
            tx_metadata={
                "payment_intent_public_id": intent.public_id,
                "provider": intent.provider,
                "provider_reference": intent.provider_reference,
            },
        )
    )
    return wallet


def adjustment(db: Session, user_id: int, amount: Decimal, reference: str | None = None, metadata: dict | None = None) -> Wallet:
    wallet = _wallet_for_update(db, user_id)
    if wallet.balance + amount < 0:
        raise HTTPException(status_code=400, detail="Balance cannot become negative")
    wallet.balance += amount
    db.add(
        WalletTransaction(
            user_id=user_id,
            type="adjustment",
            amount=amount,
            reference=reference,
            tx_metadata=metadata or {},
        )
    )
    return wallet


def hold(db: Session, user_id: int, order_id: int, amount: Decimal) -> Wallet:
    if _completed_order_tx(db, order_id, "hold"):
        return _wallet_for_update(db, user_id)
    wallet = _wallet_for_update(db, user_id)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Hold amount must be positive")
    if wallet.balance < amount:
        raise api_error(402, "INSUFFICIENT_BALANCE", "Insufficient balance")
    wallet.balance -= amount
    wallet.held_balance += amount
    db.add(WalletTransaction(user_id=user_id, order_id=order_id, type="hold", amount=amount))
    return wallet


def capture(db: Session, user_id: int, order_id: int, amount: Decimal) -> Wallet:
    if _completed_order_tx(db, order_id, "capture"):
        return _wallet_for_update(db, user_id)
    if _completed_order_tx(db, order_id, "refund"):
        raise HTTPException(status_code=409, detail="Order hold was already refunded")
    wallet = _wallet_for_update(db, user_id)
    if wallet.held_balance < amount:
        raise HTTPException(status_code=400, detail="Held balance cannot become negative")
    wallet.held_balance -= amount
    db.add(WalletTransaction(user_id=user_id, order_id=order_id, type="capture", amount=amount))
    return wallet


def refund(db: Session, user_id: int, order_id: int, amount: Decimal) -> Wallet:
    if _completed_order_tx(db, order_id, "refund"):
        return _wallet_for_update(db, user_id)
    if _completed_order_tx(db, order_id, "capture"):
        raise HTTPException(status_code=409, detail="Order hold was already captured")
    wallet = _wallet_for_update(db, user_id)
    if wallet.held_balance < amount:
        raise HTTPException(status_code=400, detail="Held balance cannot become negative")
    wallet.held_balance -= amount
    wallet.balance += amount
    db.add(WalletTransaction(user_id=user_id, order_id=order_id, type="refund", amount=amount))
    return wallet
