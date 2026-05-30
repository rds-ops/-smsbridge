from __future__ import annotations
"""operator null uniqueness

Revision ID: 0010_operator_null_unique
Revises: 0009_api_request_supplier
Create Date: 2026-05-30
"""

from alembic import op
import sqlalchemy as sa

revision = "0010_operator_null_unique"
down_revision = "0009_api_request_supplier"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM prices
                GROUP BY provider_id, service_code, country_iso2
                HAVING count(*) FILTER (WHERE operator IS NULL) > 1
            ) THEN
                RAISE EXCEPTION 'Cannot add price null-operator uniqueness: duplicate prices rows already exist';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM prices
                WHERE operator IS NOT NULL
                GROUP BY provider_id, service_code, country_iso2, operator
                HAVING count(*) > 1
            ) THEN
                RAISE EXCEPTION 'Cannot add price operator uniqueness: duplicate prices rows already exist';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM supplier_inventory
                GROUP BY supplier_id, service_code, country_iso2
                HAVING count(*) FILTER (WHERE operator IS NULL) > 1
            ) THEN
                RAISE EXCEPTION 'Cannot add supplier inventory null-operator uniqueness: duplicate rows already exist';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM supplier_inventory
                WHERE operator IS NOT NULL
                GROUP BY supplier_id, service_code, country_iso2, operator
                HAVING count(*) > 1
            ) THEN
                RAISE EXCEPTION 'Cannot add supplier inventory operator uniqueness: duplicate rows already exist';
            END IF;
        END $$;
        """
    )

    op.drop_constraint("uq_provider_price", "prices", type_="unique")
    op.drop_constraint("uq_supplier_inventory_key", "supplier_inventory", type_="unique")
    op.create_index(
        "uq_prices_provider_service_country_operator_null",
        "prices",
        ["provider_id", "service_code", "country_iso2"],
        unique=True,
        postgresql_where=sa.text("operator IS NULL"),
    )
    op.create_index(
        "uq_prices_provider_service_country_operator_value",
        "prices",
        ["provider_id", "service_code", "country_iso2", "operator"],
        unique=True,
        postgresql_where=sa.text("operator IS NOT NULL"),
    )
    op.create_index(
        "uq_supplier_inventory_supplier_service_country_operator_null",
        "supplier_inventory",
        ["supplier_id", "service_code", "country_iso2"],
        unique=True,
        postgresql_where=sa.text("operator IS NULL"),
    )
    op.create_index(
        "uq_supplier_inventory_supplier_service_country_operator_value",
        "supplier_inventory",
        ["supplier_id", "service_code", "country_iso2", "operator"],
        unique=True,
        postgresql_where=sa.text("operator IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_supplier_inventory_supplier_service_country_operator_value", table_name="supplier_inventory")
    op.drop_index("uq_supplier_inventory_supplier_service_country_operator_null", table_name="supplier_inventory")
    op.drop_index("uq_prices_provider_service_country_operator_value", table_name="prices")
    op.drop_index("uq_prices_provider_service_country_operator_null", table_name="prices")
    op.create_unique_constraint(
        "uq_supplier_inventory_key",
        "supplier_inventory",
        ["supplier_id", "service_code", "country_iso2", "operator"],
    )
    op.create_unique_constraint(
        "uq_provider_price",
        "prices",
        ["provider_id", "service_code", "country_iso2", "operator"],
    )
