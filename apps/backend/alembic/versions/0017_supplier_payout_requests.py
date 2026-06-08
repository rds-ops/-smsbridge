"""add supplier payout requests

Revision ID: 0017_supplier_payouts
Revises: 0016_payment_visibility
Create Date: 2026-06-08 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0017_supplier_payouts"
down_revision = "0016_payment_visibility"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "supplier_payout_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=36), nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 4), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("payout_method", sa.String(length=80), nullable=True),
        sa.Column("payout_address", sa.String(length=255), nullable=True),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_supplier_payout_requests_amount_positive"),
        sa.CheckConstraint(
            "status in ('requested', 'approved', 'rejected', 'cancelled', 'paid', 'failed')",
            name="ck_supplier_payout_requests_status_allowed",
        ),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_supplier_payout_requests_public_id", "supplier_payout_requests", ["public_id"], unique=True)
    op.create_index("ix_supplier_payout_requests_supplier_id", "supplier_payout_requests", ["supplier_id"], unique=False)
    op.create_index("ix_supplier_payout_requests_status", "supplier_payout_requests", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_supplier_payout_requests_status", table_name="supplier_payout_requests")
    op.drop_index("ix_supplier_payout_requests_supplier_id", table_name="supplier_payout_requests")
    op.drop_index("ix_supplier_payout_requests_public_id", table_name="supplier_payout_requests")
    op.drop_table("supplier_payout_requests")
