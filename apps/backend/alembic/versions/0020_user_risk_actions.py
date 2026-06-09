"""add user risk action history

Revision ID: 0020_user_risk_actions
Revises: 0019_api_log_buyer_key
Create Date: 2026-06-09 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0020_user_risk_actions"
down_revision = "0019_api_log_buyer_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_risk_actions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "action in ('watch', 'note', 'clear_watch', 'mark_reviewed')",
            name="ck_user_risk_actions_action_allowed",
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_risk_actions_user_id", "user_risk_actions", ["user_id"], unique=False)
    op.create_index(
        "ix_user_risk_actions_user_created_at",
        "user_risk_actions",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_user_risk_actions_user_created_at", table_name="user_risk_actions")
    op.drop_index("ix_user_risk_actions_user_id", table_name="user_risk_actions")
    op.drop_table("user_risk_actions")
