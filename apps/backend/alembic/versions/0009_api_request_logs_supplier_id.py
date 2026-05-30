from __future__ import annotations
"""api request logs supplier id

Revision ID: 0009_api_request_logs_supplier_id
Revises: 0008_provider_type_status_checks
Create Date: 2026-05-30
"""

from alembic import op
import sqlalchemy as sa

revision = "0009_api_request_logs_supplier_id"
down_revision = "0008_provider_type_status_checks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("api_request_logs", sa.Column("supplier_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_api_request_logs_supplier_id_suppliers",
        "api_request_logs",
        "suppliers",
        ["supplier_id"],
        ["id"],
    )
    op.create_index("ix_api_request_logs_supplier_id", "api_request_logs", ["supplier_id"])


def downgrade() -> None:
    op.drop_index("ix_api_request_logs_supplier_id", table_name="api_request_logs")
    op.drop_constraint("fk_api_request_logs_supplier_id_suppliers", "api_request_logs", type_="foreignkey")
    op.drop_column("api_request_logs", "supplier_id")
