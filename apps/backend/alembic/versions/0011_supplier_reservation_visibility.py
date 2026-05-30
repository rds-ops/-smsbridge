from __future__ import annotations
"""supplier reservation visibility

Revision ID: 0011_supplier_res_visibility
Revises: 0010_operator_null_unique
Create Date: 2026-05-30
"""

from alembic import op
import sqlalchemy as sa

revision = "0011_supplier_res_visibility"
down_revision = "0010_operator_null_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("supplier_inventory", sa.Column("last_reservation_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("supplier_inventory", sa.Column("last_reservation_error", sa.String(length=255), nullable=True))
    op.add_column(
        "supplier_inventory",
        sa.Column("failed_reservation_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("supplier_inventory", sa.Column("last_release_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("supplier_inventory", sa.Column("last_release_error", sa.String(length=255), nullable=True))
    op.add_column(
        "supplier_inventory",
        sa.Column("failed_release_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("supplier_inventory", "failed_release_count")
    op.drop_column("supplier_inventory", "last_release_error")
    op.drop_column("supplier_inventory", "last_release_at")
    op.drop_column("supplier_inventory", "failed_reservation_count")
    op.drop_column("supplier_inventory", "last_reservation_error")
    op.drop_column("supplier_inventory", "last_reservation_at")
