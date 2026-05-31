"""add payment intent lifecycle visibility

Revision ID: 0016_payment_visibility
Revises: 0015_payment_wallet_tx
Create Date: 2026-05-31 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0016_payment_visibility"
down_revision = "0015_payment_wallet_tx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payment_intents", sa.Column("last_webhook_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("payment_intents", sa.Column("last_webhook_event_id", sa.String(length=255), nullable=True))
    op.add_column("payment_intents", sa.Column("last_webhook_status", sa.String(length=40), nullable=True))
    op.add_column("payment_intents", sa.Column("last_webhook_error", sa.String(length=255), nullable=True))
    op.add_column("payment_intents", sa.Column("failed_reason", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("payment_intents", "failed_reason")
    op.drop_column("payment_intents", "last_webhook_error")
    op.drop_column("payment_intents", "last_webhook_status")
    op.drop_column("payment_intents", "last_webhook_event_id")
    op.drop_column("payment_intents", "last_webhook_at")
