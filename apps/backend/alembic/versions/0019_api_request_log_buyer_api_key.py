"""add buyer api key request log attribution

Revision ID: 0019_api_log_buyer_key
Revises: 0018_buyer_api_keys
Create Date: 2026-06-08 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0019_api_log_buyer_key"
down_revision = "0018_buyer_api_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("api_request_logs", sa.Column("buyer_api_key_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_api_request_logs_buyer_api_key_id_buyer_api_keys",
        "api_request_logs",
        "buyer_api_keys",
        ["buyer_api_key_id"],
        ["id"],
    )
    op.create_index("ix_api_request_logs_buyer_api_key_id", "api_request_logs", ["buyer_api_key_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_api_request_logs_buyer_api_key_id", table_name="api_request_logs")
    op.drop_constraint(
        "fk_api_request_logs_buyer_api_key_id_buyer_api_keys",
        "api_request_logs",
        type_="foreignkey",
    )
    op.drop_column("api_request_logs", "buyer_api_key_id")
