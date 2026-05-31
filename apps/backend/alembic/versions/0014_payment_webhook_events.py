from __future__ import annotations
"""payment webhook events

Revision ID: 0014_payment_webhook_events
Revises: 0013_payment_intents
Create Date: 2026-05-31
"""

from alembic import op
import sqlalchemy as sa

revision = "0014_payment_webhook_events"
down_revision = "0013_payment_intents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payment_intents", sa.Column("succeeded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("payment_intents", sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("payment_intents", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "payment_webhook_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("external_event_id", sa.String(length=255), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status in ('processed', 'duplicate', 'ignored', 'failed')",
            name="ck_payment_webhook_events_status_allowed",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "payload_hash", name="uq_payment_webhook_events_provider_payload_hash"),
    )
    op.create_index("ix_payment_webhook_events_provider", "payment_webhook_events", ["provider"])
    op.create_index("ix_payment_webhook_events_status", "payment_webhook_events", ["status"])
    op.create_index(
        "uq_payment_webhook_events_provider_external_event_id",
        "payment_webhook_events",
        ["provider", "external_event_id"],
        unique=True,
        postgresql_where=sa.text("external_event_id IS NOT NULL"),
        sqlite_where=sa.text("external_event_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_payment_webhook_events_provider_external_event_id", table_name="payment_webhook_events")
    op.drop_index("ix_payment_webhook_events_status", table_name="payment_webhook_events")
    op.drop_index("ix_payment_webhook_events_provider", table_name="payment_webhook_events")
    op.drop_table("payment_webhook_events")
    op.drop_column("payment_intents", "cancelled_at")
    op.drop_column("payment_intents", "failed_at")
    op.drop_column("payment_intents", "succeeded_at")

