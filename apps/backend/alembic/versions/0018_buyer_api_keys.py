"""add buyer api keys

Revision ID: 0018_buyer_api_keys
Revises: 0017_supplier_payouts
Create Date: 2026-06-08 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0018_buyer_api_keys"
down_revision = "0017_supplier_payouts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "buyer_api_keys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=True),
        sa.Column("key_hash", sa.String(length=128), nullable=False),
        sa.Column("key_prefix", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status in ('active', 'revoked')", name="ck_buyer_api_keys_status_allowed"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_buyer_api_keys_public_id", "buyer_api_keys", ["public_id"], unique=True)
    op.create_index("ix_buyer_api_keys_user_id", "buyer_api_keys", ["user_id"], unique=False)
    op.create_index("ix_buyer_api_keys_status", "buyer_api_keys", ["status"], unique=False)
    op.create_index("uq_buyer_api_keys_key_hash", "buyer_api_keys", ["key_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_buyer_api_keys_key_hash", table_name="buyer_api_keys")
    op.drop_index("ix_buyer_api_keys_status", table_name="buyer_api_keys")
    op.drop_index("ix_buyer_api_keys_user_id", table_name="buyer_api_keys")
    op.drop_index("ix_buyer_api_keys_public_id", table_name="buyer_api_keys")
    op.drop_table("buyer_api_keys")
