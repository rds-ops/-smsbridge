"""add request id to api request logs

Revision ID: 0021_request_id_logs
Revises: 0020_user_risk_actions
Create Date: 2026-06-09 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0021_request_id_logs"
down_revision = "0020_user_risk_actions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("api_request_logs", sa.Column("request_id", sa.String(length=128), nullable=True))
    op.create_index("ix_api_request_logs_request_id", "api_request_logs", ["request_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_api_request_logs_request_id", table_name="api_request_logs")
    op.drop_column("api_request_logs", "request_id")
