"""add login attempts lockout table

Revision ID: 0024_login_attempts
Revises: 0023_refresh_sessions
Create Date: 2026-06-29 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0024_login_attempts"
down_revision = "0023_refresh_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "login_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("identifier_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("failed_attempts", sa.Integer(), nullable=False),
        sa.Column("first_failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("failed_attempts >= 0", name="ck_login_attempts_failed_attempts_non_negative"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("identifier_hash"),
    )
    op.create_index("ix_login_attempts_locked_until", "login_attempts", ["locked_until"], unique=False)
    op.create_index("ix_login_attempts_user_id", "login_attempts", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_login_attempts_user_id", table_name="login_attempts")
    op.drop_index("ix_login_attempts_locked_until", table_name="login_attempts")
    op.drop_table("login_attempts")
