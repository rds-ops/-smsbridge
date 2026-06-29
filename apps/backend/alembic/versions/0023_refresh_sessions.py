"""add refresh sessions

Revision ID: 0023_refresh_sessions
Revises: 0022_obs_index_audit
Create Date: 2026-06-29 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0023_refresh_sessions"
down_revision = "0022_obs_index_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "refresh_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("jti", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("jti"),
    )
    op.create_index("ix_refresh_sessions_user_id", "refresh_sessions", ["user_id"], unique=False)
    op.create_index("ix_refresh_sessions_expires_at", "refresh_sessions", ["expires_at"], unique=False)
    op.create_index("ix_refresh_sessions_revoked_at", "refresh_sessions", ["revoked_at"], unique=False)
    op.create_index(
        "ix_refresh_sessions_user_created_at",
        "refresh_sessions",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_refresh_sessions_user_revoked_at",
        "refresh_sessions",
        ["user_id", "revoked_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_refresh_sessions_user_revoked_at", table_name="refresh_sessions")
    op.drop_index("ix_refresh_sessions_user_created_at", table_name="refresh_sessions")
    op.drop_index("ix_refresh_sessions_revoked_at", table_name="refresh_sessions")
    op.drop_index("ix_refresh_sessions_expires_at", table_name="refresh_sessions")
    op.drop_index("ix_refresh_sessions_user_id", table_name="refresh_sessions")
    op.drop_table("refresh_sessions")
