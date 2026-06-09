"""add observability query indexes

Revision ID: 0022_obs_index_audit
Revises: 0021_request_id_logs
Create Date: 2026-06-09 00:00:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "0022_obs_index_audit"
down_revision = "0021_request_id_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_orders_user_created_at", "orders", ["user_id", "created_at"], unique=False)
    op.create_index("ix_orders_status_expires_at", "orders", ["status", "expires_at"], unique=False)
    op.create_index("ix_orders_status_created_at", "orders", ["status", "created_at"], unique=False)

    op.create_index("ix_order_events_order_created_at", "order_events", ["order_id", "created_at"], unique=False)

    op.create_index(
        "ix_api_request_logs_user_created_at",
        "api_request_logs",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_api_request_logs_supplier_created_at",
        "api_request_logs",
        ["supplier_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_api_request_logs_buyer_key_created_at",
        "api_request_logs",
        ["buyer_api_key_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_api_request_logs_status_created_at",
        "api_request_logs",
        ["status_code", "created_at"],
        unique=False,
    )

    op.create_index(
        "ix_payment_intents_user_created_at",
        "payment_intents",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_payment_intents_status_created_at",
        "payment_intents",
        ["status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_payment_intents_provider_created_at",
        "payment_intents",
        ["provider", "created_at"],
        unique=False,
    )

    op.create_index(
        "ix_supplier_inventory_supplier_updated_at",
        "supplier_inventory",
        ["supplier_id", "updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_supplier_inventory_lookup_active",
        "supplier_inventory",
        ["status", "service_code", "country_iso2", "operator"],
        unique=False,
    )

    op.create_index(
        "ix_supplier_activations_supplier_created_at",
        "supplier_activations",
        ["supplier_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_supplier_activations_supplier_phone_status",
        "supplier_activations",
        ["supplier_id", "phone_number", "status"],
        unique=False,
    )

    op.create_index(
        "ix_supplier_payout_requests_supplier_created_at",
        "supplier_payout_requests",
        ["supplier_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_supplier_payout_requests_status_created_at",
        "supplier_payout_requests",
        ["status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_supplier_payout_requests_status_updated_at",
        "supplier_payout_requests",
        ["status", "updated_at"],
        unique=False,
    )

    op.create_index("ix_sms_messages_order_created_at", "sms_messages", ["order_id", "created_at"], unique=False)
    op.create_index("ix_sms_messages_provider_created_at", "sms_messages", ["provider_id", "created_at"], unique=False)

    op.create_index(
        "ix_supplier_transactions_supplier_created_at",
        "supplier_transactions",
        ["supplier_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_supplier_transactions_reference_type_status",
        "supplier_transactions",
        ["reference", "type", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_supplier_transactions_reference_type_status", table_name="supplier_transactions")
    op.drop_index("ix_supplier_transactions_supplier_created_at", table_name="supplier_transactions")
    op.drop_index("ix_sms_messages_provider_created_at", table_name="sms_messages")
    op.drop_index("ix_sms_messages_order_created_at", table_name="sms_messages")
    op.drop_index("ix_supplier_payout_requests_status_updated_at", table_name="supplier_payout_requests")
    op.drop_index("ix_supplier_payout_requests_status_created_at", table_name="supplier_payout_requests")
    op.drop_index("ix_supplier_payout_requests_supplier_created_at", table_name="supplier_payout_requests")
    op.drop_index("ix_supplier_activations_supplier_phone_status", table_name="supplier_activations")
    op.drop_index("ix_supplier_activations_supplier_created_at", table_name="supplier_activations")
    op.drop_index("ix_supplier_inventory_lookup_active", table_name="supplier_inventory")
    op.drop_index("ix_supplier_inventory_supplier_updated_at", table_name="supplier_inventory")
    op.drop_index("ix_payment_intents_provider_created_at", table_name="payment_intents")
    op.drop_index("ix_payment_intents_status_created_at", table_name="payment_intents")
    op.drop_index("ix_payment_intents_user_created_at", table_name="payment_intents")
    op.drop_index("ix_api_request_logs_status_created_at", table_name="api_request_logs")
    op.drop_index("ix_api_request_logs_buyer_key_created_at", table_name="api_request_logs")
    op.drop_index("ix_api_request_logs_supplier_created_at", table_name="api_request_logs")
    op.drop_index("ix_api_request_logs_user_created_at", table_name="api_request_logs")
    op.drop_index("ix_order_events_order_created_at", table_name="order_events")
    op.drop_index("ix_orders_status_created_at", table_name="orders")
    op.drop_index("ix_orders_status_expires_at", table_name="orders")
    op.drop_index("ix_orders_user_created_at", table_name="orders")
