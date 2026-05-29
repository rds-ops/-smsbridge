from __future__ import annotations
"""generic sms messages

Revision ID: 0005_sms_messages
Revises: 0004_order_create_idempotency
Create Date: 2026-05-29
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_sms_messages"
down_revision = "0004_order_create_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sms_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=True),
        sa.Column("supplier_activation_id", sa.Integer(), sa.ForeignKey("supplier_activations.id"), nullable=True),
        sa.Column("provider_id", sa.Integer(), sa.ForeignKey("providers.id"), nullable=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("external_message_id", sa.String(120), nullable=True),
        sa.Column("phone_number", sa.String(40), nullable=True),
        sa.Column("phone_from", sa.String(120), nullable=True),
        sa.Column("text", sa.String(1000), nullable=False),
        sa.Column("parsed_code", sa.String(20), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source", "supplier_id", "external_message_id", name="uq_sms_messages_source_supplier_external_id"),
    )
    op.create_index("ix_sms_messages_order_id", "sms_messages", ["order_id"])
    op.create_index("ix_sms_messages_supplier_id", "sms_messages", ["supplier_id"])
    op.create_index("ix_sms_messages_provider_id", "sms_messages", ["provider_id"])
    op.create_index("ix_sms_messages_created_at", "sms_messages", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_sms_messages_created_at", table_name="sms_messages")
    op.drop_index("ix_sms_messages_provider_id", table_name="sms_messages")
    op.drop_index("ix_sms_messages_supplier_id", table_name="sms_messages")
    op.drop_index("ix_sms_messages_order_id", table_name="sms_messages")
    op.drop_table("sms_messages")
