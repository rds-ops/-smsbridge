"""link wallet deposits to payment intents

Revision ID: 0015_payment_wallet_tx
Revises: 0014_payment_webhook_events
Create Date: 2026-05-31 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0015_payment_wallet_tx"
down_revision = "0014_payment_webhook_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("wallet_transactions", sa.Column("payment_intent_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_wallet_transactions_payment_intent_id_payment_intents",
        "wallet_transactions",
        "payment_intents",
        ["payment_intent_id"],
        ["id"],
    )
    op.create_index(
        "ix_wallet_transactions_payment_intent_id",
        "wallet_transactions",
        ["payment_intent_id"],
        unique=False,
    )
    op.create_index(
        "uq_wallet_transactions_payment_intent_id_not_null",
        "wallet_transactions",
        ["payment_intent_id"],
        unique=True,
        postgresql_where=sa.text("payment_intent_id IS NOT NULL"),
        sqlite_where=sa.text("payment_intent_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_wallet_transactions_payment_intent_id_not_null", table_name="wallet_transactions")
    op.drop_index("ix_wallet_transactions_payment_intent_id", table_name="wallet_transactions")
    op.drop_constraint(
        "fk_wallet_transactions_payment_intent_id_payment_intents",
        "wallet_transactions",
        type_="foreignkey",
    )
    op.drop_column("wallet_transactions", "payment_intent_id")
