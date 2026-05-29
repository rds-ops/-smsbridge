from __future__ import annotations
"""supplier reservation config

Revision ID: 0006_supplier_reservation_config
Revises: 0005_sms_messages
Create Date: 2026-05-29
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_supplier_reservation_config"
down_revision = "0005_sms_messages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("suppliers", sa.Column("reservation_url", sa.String(1000), nullable=True))
    op.add_column("suppliers", sa.Column("reservation_auth_type", sa.String(50), nullable=True))
    op.add_column("suppliers", sa.Column("reservation_auth_secret_encrypted", sa.String(1000), nullable=True))
    op.add_column("suppliers", sa.Column("reservation_timeout_seconds", sa.Integer(), nullable=True))
    op.add_column(
        "suppliers",
        sa.Column("reservation_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("suppliers", "reservation_enabled")
    op.drop_column("suppliers", "reservation_timeout_seconds")
    op.drop_column("suppliers", "reservation_auth_secret_encrypted")
    op.drop_column("suppliers", "reservation_auth_type")
    op.drop_column("suppliers", "reservation_url")
