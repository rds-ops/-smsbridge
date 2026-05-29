from __future__ import annotations
"""order create idempotency keys

Revision ID: 0004_order_create_idempotency
Revises: 0003_non_negative_balances
Create Date: 2026-05-29
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_order_create_idempotency"
down_revision = "0003_non_negative_balances"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="in_progress"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "action", "key", name="uq_idempotency_user_action_key"),
    )
    op.create_index("ix_idempotency_keys_user_id", "idempotency_keys", ["user_id"])
    op.create_index("ix_idempotency_keys_order_id", "idempotency_keys", ["order_id"])


def downgrade() -> None:
    op.drop_index("ix_idempotency_keys_order_id", table_name="idempotency_keys")
    op.drop_index("ix_idempotency_keys_user_id", table_name="idempotency_keys")
    op.drop_table("idempotency_keys")
