"""add supplier applications

Revision ID: 0025_supplier_applications
Revises: 0024_login_attempts
Create Date: 2026-06-30 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0025_supplier_applications"
down_revision = "0024_login_attempts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "supplier_applications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("contact_name", sa.String(length=160), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("contact_handle", sa.String(length=160), nullable=False),
        sa.Column("country_market", sa.String(length=120), nullable=False),
        sa.Column("number_type", sa.String(length=40), nullable=False),
        sa.Column("estimated_daily_volume", sa.Integer(), nullable=False),
        sa.Column("estimated_monthly_volume", sa.Integer(), nullable=False),
        sa.Column("integration_availability", sa.String(length=40), nullable=False),
        sa.Column("inventory_description", sa.Text(), nullable=False),
        sa.Column("api_url", sa.String(length=1000), nullable=True),
        sa.Column("equipment_details", sa.Text(), nullable=True),
        sa.Column("website", sa.String(length=1000), nullable=True),
        sa.Column("internal_review_note", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status in ('pending', 'approved', 'rejected', 'needs_info')",
            name="ck_supplier_applications_status_allowed",
        ),
        sa.CheckConstraint(
            "number_type in ('real_sim', 'virtual_numbers', 'other')",
            name="ck_supplier_applications_number_type_allowed",
        ),
        sa.CheckConstraint(
            "integration_availability in ('yes', 'no', 'needs_discussion')",
            name="ck_supplier_applications_integration_allowed",
        ),
        sa.CheckConstraint(
            "estimated_daily_volume >= 0",
            name="ck_supplier_applications_daily_volume_non_negative",
        ),
        sa.CheckConstraint(
            "estimated_monthly_volume >= 0",
            name="ck_supplier_applications_monthly_volume_non_negative",
        ),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id"),
    )
    op.create_index("ix_supplier_applications_public_id", "supplier_applications", ["public_id"], unique=False)
    op.create_index("ix_supplier_applications_status", "supplier_applications", ["status"], unique=False)
    op.create_index("ix_supplier_applications_email", "supplier_applications", ["email"], unique=False)
    op.create_index(
        "ix_supplier_applications_status_created_at",
        "supplier_applications",
        ["status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_supplier_applications_email_created_at",
        "supplier_applications",
        ["email", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_supplier_applications_email_created_at", table_name="supplier_applications")
    op.drop_index("ix_supplier_applications_status_created_at", table_name="supplier_applications")
    op.drop_index("ix_supplier_applications_email", table_name="supplier_applications")
    op.drop_index("ix_supplier_applications_status", table_name="supplier_applications")
    op.drop_index("ix_supplier_applications_public_id", table_name="supplier_applications")
    op.drop_table("supplier_applications")
