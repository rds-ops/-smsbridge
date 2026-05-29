from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Provider
from app.providers.router import get_adapter


def test_admin_create_provider_rejects_invalid_type(client, admin_token):
    response = client.post(
        "/admin/providers",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": "Bad Provider", "code": "bad_provider", "type": "bad_type", "status": "active"},
    )

    assert response.status_code == 422


def test_admin_update_provider_rejects_invalid_status(client, admin_token):
    db = SessionLocal()
    try:
        provider_id = db.scalar(select(Provider.id).where(Provider.code == "mock"))
    finally:
        db.close()

    response = client.patch(
        f"/admin/providers/{provider_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": "MockProvider", "code": "mock", "type": "mock", "status": "paused"},
    )

    assert response.status_code == 422


def test_seed_provider_values_are_valid():
    db = SessionLocal()
    try:
        mock = db.scalar(select(Provider).where(Provider.code == "mock"))
        supplier_pool = db.scalar(select(Provider).where(Provider.code == "supplier_pool"))
        assert mock.type == "mock"
        assert mock.status == "active"
        assert supplier_pool.type == "supplier_pool"
        assert supplier_pool.status == "active"
    finally:
        db.close()


def test_provider_router_rejects_unknown_provider_type_safely():
    provider = Provider(name="Unknown", code="unknown", type="unknown_type", status="active")

    with pytest.raises(HTTPException) as exc:
        get_adapter(provider)

    assert exc.value.status_code == 502
    assert exc.value.detail["code"] == "PROVIDER_UNAVAILABLE"
