from __future__ import annotations
"""supplier release retry queue

Revision ID: 0012_supplier_release_retries
Revises: 0011_supplier_res_visibility
Create Date: 2026-05-30
"""

from alembic import op
import sqlalchemy as sa

revision = "0012_supplier_release_retries"
down_revision = "0011_supplier_res_visibility"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "supplier_release_retries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("supplier_activation_id", sa.Integer(), nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("retry_type", sa.String(length=20), nullable=False, server_default="release"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("reason", sa.String(length=20), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_error", sa.String(length=255), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("attempt_count >= 0", name="ck_supplier_release_retries_attempt_count_non_negative"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["supplier_activation_id"], ["supplier_activations.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("supplier_activation_id", "retry_type", name="uq_supplier_release_retry_activation_type"),
    )
    op.create_index("ix_supplier_release_retries_order_id", "supplier_release_retries", ["order_id"])
    op.create_index("ix_supplier_release_retries_supplier_id", "supplier_release_retries", ["supplier_id"])
    op.create_index("ix_supplier_release_retries_status", "supplier_release_retries", ["status"])
    op.create_index("ix_supplier_release_retries_next_retry_at", "supplier_release_retries", ["next_retry_at"])
    op.create_index(
        "ix_supplier_release_retries_status_next_retry_at",
        "supplier_release_retries",
        ["status", "next_retry_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_supplier_release_retries_status_next_retry_at", table_name="supplier_release_retries")
    op.drop_index("ix_supplier_release_retries_next_retry_at", table_name="supplier_release_retries")
    op.drop_index("ix_supplier_release_retries_status", table_name="supplier_release_retries")
    op.drop_index("ix_supplier_release_retries_supplier_id", table_name="supplier_release_retries")
    op.drop_index("ix_supplier_release_retries_order_id", table_name="supplier_release_retries")
    op.drop_table("supplier_release_retries")

