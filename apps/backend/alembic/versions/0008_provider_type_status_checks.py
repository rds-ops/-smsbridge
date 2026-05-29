from __future__ import annotations
"""provider type status checks

Revision ID: 0008_provider_type_status_checks
Revises: 0007_order_events
Create Date: 2026-05-29
"""

from alembic import op

revision = "0008_provider_type_status_checks"
down_revision = "0007_order_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_providers_type_allowed",
        "providers",
        "type in ('mock', 'supplier_pool', 'five_sim', 'sms_activate', 'sms_man')",
    )
    op.create_check_constraint(
        "ck_providers_status_allowed",
        "providers",
        "status in ('active', 'inactive', 'disabled')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_providers_status_allowed", "providers", type_="check")
    op.drop_constraint("ck_providers_type_allowed", "providers", type_="check")
