from __future__ import annotations
"""payment intents skeleton

Revision ID: 0013_payment_intents
Revises: 0012_supplier_release_retries
Create Date: 2026-05-31
"""

from alembic import op
import sqlalchemy as sa

revision = "0013_payment_intents"
down_revision = "0012_supplier_release_retries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_intents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="created"),
        sa.Column("provider_reference", sa.String(length=255), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("request_hash", sa.String(length=64), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("amount > 0", name="ck_payment_intents_amount_positive"),
        sa.CheckConstraint(
            "status in ('created', 'pending', 'succeeded', 'failed', 'cancelled', 'expired')",
            name="ck_payment_intents_status_allowed",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payment_intents_public_id", "payment_intents", ["public_id"], unique=True)
    op.create_index("ix_payment_intents_status", "payment_intents", ["status"], unique=False)
    op.create_index("ix_payment_intents_user_id", "payment_intents", ["user_id"], unique=False)
    op.create_index(
        "uq_payment_intents_user_idempotency_key_not_null",
        "payment_intents",
        ["user_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
        sqlite_where=sa.text("idempotency_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_payment_intents_user_idempotency_key_not_null", table_name="payment_intents")
    op.drop_index("ix_payment_intents_user_id", table_name="payment_intents")
    op.drop_index("ix_payment_intents_status", table_name="payment_intents")
    op.drop_index("ix_payment_intents_public_id", table_name="payment_intents")
    op.drop_table("payment_intents")
