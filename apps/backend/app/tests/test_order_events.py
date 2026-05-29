from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.jobs.tasks import poll_waiting_orders
from app.models import Order, OrderEvent, Provider
from app.services.order_state import InvalidOrderTransition, OrderStatus, transition_order


def create_local_order() -> Order:
    db = SessionLocal()
    try:
        provider = db.scalar(select(Provider).where(Provider.code == "mock"))
        order = Order(
            user_id=2,
            provider_id=provider.id,
            service_code="telegram",
            country_iso2="ID",
            status=OrderStatus.CREATED,
            price=Decimal("0.5000"),
            provider_cost=Decimal("0.3500"),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        db.add(order)
        db.flush()
        order_id = order.id
        db.commit()
        return db.get(Order, order_id)
    finally:
        db.close()


def event_count(db) -> int:
    return db.scalar(select(func.count(OrderEvent.id)))


def test_transition_order_creates_order_event():
    order = create_local_order()
    db = SessionLocal()
    try:
        order = db.get(Order, order.id)
        transition_order(
            order,
            OrderStatus.WAITING_SMS,
            db=db,
            actor_type="system",
            reason="test_transition",
            metadata={"source": "test"},
        )
        db.commit()

        event = db.scalar(select(OrderEvent).where(OrderEvent.order_id == order.id))
        assert event.old_status == OrderStatus.CREATED
        assert event.new_status == OrderStatus.WAITING_SMS
        assert event.actor_type == "system"
        assert event.reason == "test_transition"
        assert event.event_metadata == {"source": "test"}
    finally:
        db.close()


def test_invalid_transition_does_not_create_order_event():
    order = create_local_order()
    db = SessionLocal()
    try:
        order = db.get(Order, order.id)
        before = event_count(db)
        with pytest.raises(InvalidOrderTransition):
            transition_order(order, OrderStatus.COMPLETED, db=db, actor_type="system", reason="invalid")
        db.rollback()
        assert event_count(db) == before
    finally:
        db.close()


def test_repeated_same_status_transition_does_not_create_duplicate_event():
    order = create_local_order()
    db = SessionLocal()
    try:
        order = db.get(Order, order.id)
        transition_order(order, OrderStatus.WAITING_SMS, db=db, actor_type="system", reason="first")
        transition_order(order, OrderStatus.WAITING_SMS, db=db, actor_type="system", reason="repeat")
        db.commit()
        events = list(db.scalars(select(OrderEvent).where(OrderEvent.order_id == order.id)))
        assert len(events) == 1
        assert events[0].reason == "first"
    finally:
        db.close()


def test_cancel_path_creates_order_event(client, user_token):
    order = client.post(
        "/api/v1/orders",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"service_code": "telegram", "country_iso2": "ID"},
    ).json()

    response = client.post(f"/api/v1/orders/{order['public_id']}/cancel", headers={"Authorization": f"Bearer {user_token}"})

    assert response.status_code == 200, response.text
    db = SessionLocal()
    try:
        order_entity = db.scalar(select(Order).where(Order.public_id == order["public_id"]))
        events = list(db.scalars(select(OrderEvent).where(OrderEvent.order_id == order_entity.id).order_by(OrderEvent.id)))
        assert [event.new_status for event in events] == [OrderStatus.WAITING_SMS, OrderStatus.CANCELLED]
        assert events[-1].actor_type == "buyer"
        assert events[-1].actor_user_id == 2
        assert events[-1].reason == "buyer_cancelled"
    finally:
        db.close()


def test_expire_path_creates_order_event(client, user_token):
    order = client.post(
        "/api/v1/orders",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"service_code": "telegram", "country_iso2": "ID"},
    ).json()
    db = SessionLocal()
    try:
        order_entity = db.scalar(select(Order).where(Order.public_id == order["public_id"]))
        order_entity.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    finally:
        db.close()

    poll_waiting_orders()

    db = SessionLocal()
    try:
        order_entity = db.scalar(select(Order).where(Order.public_id == order["public_id"]))
        event = db.scalar(
            select(OrderEvent).where(
                OrderEvent.order_id == order_entity.id,
                OrderEvent.new_status == OrderStatus.EXPIRED,
            )
        )
        assert event.actor_type == "worker"
        assert event.reason == "timeout"
    finally:
        db.close()


def test_finish_path_creates_order_event(client, user_token):
    order = client.post(
        "/api/v1/orders",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"service_code": "telegram", "country_iso2": "ID"},
    ).json()
    poll_waiting_orders()

    response = client.post(f"/api/v1/orders/{order['public_id']}/finish", headers={"Authorization": f"Bearer {user_token}"})

    assert response.status_code == 200, response.text
    db = SessionLocal()
    try:
        order_entity = db.scalar(select(Order).where(Order.public_id == order["public_id"]))
        events = list(db.scalars(select(OrderEvent).where(OrderEvent.order_id == order_entity.id).order_by(OrderEvent.id)))
        assert [event.new_status for event in events] == [
            OrderStatus.WAITING_SMS,
            OrderStatus.SMS_RECEIVED,
            OrderStatus.COMPLETED,
        ]
        assert events[-1].actor_type == "buyer"
        assert events[-1].reason == "buyer_finished"
    finally:
        db.close()


def test_admin_can_view_order_events(client, admin_token, user_token):
    order = client.post(
        "/api/v1/orders",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"service_code": "telegram", "country_iso2": "ID"},
    ).json()
    db = SessionLocal()
    try:
        order_id = db.scalar(select(Order.id).where(Order.public_id == order["public_id"]))
    finally:
        db.close()

    response = client.get(f"/admin/orders/{order_id}/events", headers={"Authorization": f"Bearer {admin_token}"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 1
    assert body[0]["order_id"] == order_id
    assert body[0]["old_status"] == OrderStatus.CREATED
    assert body[0]["new_status"] == OrderStatus.WAITING_SMS
