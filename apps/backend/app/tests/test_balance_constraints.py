from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal
from app.models import Supplier, Wallet


@pytest.mark.parametrize("field", ["balance", "held_balance"])
def test_database_rejects_negative_wallet_balances(field):
    db = SessionLocal()
    try:
        with pytest.raises(IntegrityError):
            db.execute(update(Wallet).where(Wallet.user_id == 2).values({field: Decimal("-0.0001")}))
            db.commit()
    finally:
        db.rollback()
        db.close()


@pytest.mark.parametrize("field", ["balance", "held_balance"])
def test_database_rejects_negative_supplier_balances(field):
    db = SessionLocal()
    try:
        supplier = Supplier(name="Constraint Test Supplier", status="active")
        setattr(supplier, field, Decimal("-0.0001"))
        db.add(supplier)
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()
