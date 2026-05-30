from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal
from app.models import Price, Provider, Supplier, SupplierInventory


def create_supplier(client, admin_token) -> tuple[dict, str]:
    created = client.post(
        "/admin/suppliers",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": "Operator Supplier", "email": "operator@example.com", "status": "active", "reward_percent": "70.00"},
    )
    assert created.status_code == 200, created.text
    supplier = created.json()
    key = client.post(
        f"/admin/suppliers/{supplier['id']}/api-key/regenerate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert key.status_code == 200, key.text
    return supplier, key.json()["api_key"]


def update_inventory(client, api_key: str, *, operator: str | None, count: int):
    return client.post(
        "/supplier/v1/inventory/update",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "items": [
                {
                    "service_code": "telegram",
                    "country_iso2": "ID",
                    "operator": operator,
                    "available_count": count,
                    "success_rate": "95.00",
                    "avg_sms_time_seconds": 30,
                    "status": "active",
                }
            ]
        },
    )


def test_database_rejects_duplicate_null_operator_price():
    db = SessionLocal()
    try:
        provider = db.scalar(select(Provider).where(Provider.code == "mock"))
        db.add(
            Price(
                provider_id=provider.id,
                service_code="telegram",
                country_iso2="ID",
                operator=None,
                provider_cost=Decimal("0.3500"),
                final_price=Decimal("0.4375"),
                available_count=1,
                delivery_rate=Decimal("90.00"),
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()


def test_database_rejects_duplicate_null_operator_supplier_inventory():
    db = SessionLocal()
    try:
        supplier = Supplier(name="Duplicate Null Supplier", status="active")
        db.add(supplier)
        db.flush()
        db.add_all(
            [
                SupplierInventory(
                    supplier_id=supplier.id,
                    service_code="telegram",
                    country_iso2="ID",
                    operator=None,
                    available_count=1,
                ),
                SupplierInventory(
                    supplier_id=supplier.id,
                    service_code="telegram",
                    country_iso2="ID",
                    operator=None,
                    available_count=2,
                ),
            ]
        )
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()


def test_non_null_operators_remain_distinct_for_prices():
    db = SessionLocal()
    try:
        provider = db.scalar(select(Provider).where(Provider.code == "mock"))
        db.add_all(
            [
                Price(
                    provider_id=provider.id,
                    service_code="telegram",
                    country_iso2="ID",
                    operator="beeline",
                    provider_cost=Decimal("0.3500"),
                    final_price=Decimal("0.4375"),
                    available_count=1,
                    delivery_rate=Decimal("90.00"),
                ),
                Price(
                    provider_id=provider.id,
                    service_code="telegram",
                    country_iso2="ID",
                    operator="ucell",
                    provider_cost=Decimal("0.3600"),
                    final_price=Decimal("0.4500"),
                    available_count=1,
                    delivery_rate=Decimal("90.00"),
                ),
            ]
        )
        db.commit()
    finally:
        db.close()


def test_null_operator_and_named_operator_can_coexist_for_supplier_inventory():
    db = SessionLocal()
    try:
        supplier = Supplier(name="Mixed Operator Supplier", status="active")
        db.add(supplier)
        db.flush()
        db.add_all(
            [
                SupplierInventory(
                    supplier_id=supplier.id,
                    service_code="telegram",
                    country_iso2="ID",
                    operator=None,
                    available_count=1,
                ),
                SupplierInventory(
                    supplier_id=supplier.id,
                    service_code="telegram",
                    country_iso2="ID",
                    operator="beeline",
                    available_count=1,
                ),
            ]
        )
        db.commit()
    finally:
        db.close()


def test_supplier_inventory_update_with_null_operator_updates_existing_row(client, admin_token):
    supplier, api_key = create_supplier(client, admin_token)

    first = update_inventory(client, api_key, operator="any", count=5)
    second = update_inventory(client, api_key, operator=None, count=9)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    db = SessionLocal()
    try:
        rows = list(
            db.scalars(
                select(SupplierInventory).where(
                    SupplierInventory.supplier_id == supplier["id"],
                    SupplierInventory.service_code == "telegram",
                    SupplierInventory.country_iso2 == "ID",
                    SupplierInventory.operator.is_(None),
                )
            )
        )
        assert len(rows) == 1
        assert rows[0].available_count == 9
    finally:
        db.close()


def test_supplier_pool_price_sync_does_not_create_duplicate_null_operator_rows(client, admin_token):
    _supplier, api_key = create_supplier(client, admin_token)

    assert update_inventory(client, api_key, operator="any", count=5).status_code == 200
    assert update_inventory(client, api_key, operator=None, count=7).status_code == 200

    db = SessionLocal()
    try:
        supplier_pool = db.scalar(select(Provider).where(Provider.code == "supplier_pool"))
        price_count = db.scalar(
            select(func.count(Price.id)).where(
                Price.provider_id == supplier_pool.id,
                Price.service_code == "telegram",
                Price.country_iso2 == "ID",
                Price.operator.is_(None),
            )
        )
        assert price_count == 1
    finally:
        db.close()
