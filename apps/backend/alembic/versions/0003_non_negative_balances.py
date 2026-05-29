from __future__ import annotations
"""non-negative balance constraints

Revision ID: 0003_non_negative_balances
Revises: 0002_supplier_module
Create Date: 2026-05-29
"""

from alembic import op

revision = "0003_non_negative_balances"
down_revision = "0002_supplier_module"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint("ck_wallets_balance_non_negative", "wallets", "balance >= 0")
    op.create_check_constraint("ck_wallets_held_balance_non_negative", "wallets", "held_balance >= 0")
    op.create_check_constraint("ck_suppliers_balance_non_negative", "suppliers", "balance >= 0")
    op.create_check_constraint("ck_suppliers_held_balance_non_negative", "suppliers", "held_balance >= 0")


def downgrade() -> None:
    op.drop_constraint("ck_suppliers_held_balance_non_negative", "suppliers", type_="check")
    op.drop_constraint("ck_suppliers_balance_non_negative", "suppliers", type_="check")
    op.drop_constraint("ck_wallets_held_balance_non_negative", "wallets", type_="check")
    op.drop_constraint("ck_wallets_balance_non_negative", "wallets", type_="check")
