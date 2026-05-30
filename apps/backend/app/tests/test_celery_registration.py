from __future__ import annotations

from sqlalchemy.dialects import postgresql

from app.jobs.celery_app import celery_app, registered_smsbridge_tasks
from app.jobs.tasks import poll_waiting_orders, retry_supplier_releases, waiting_orders_polling_query


def test_poll_waiting_orders_is_registered():
    assert "app.jobs.tasks.poll_waiting_orders" in celery_app.tasks
    assert "app.jobs.tasks.poll_waiting_orders" in registered_smsbridge_tasks()


def test_retry_supplier_releases_is_registered():
    assert "app.jobs.tasks.retry_supplier_releases" in celery_app.tasks
    assert "app.jobs.tasks.retry_supplier_releases" in registered_smsbridge_tasks()


def test_poll_waiting_orders_executes_successfully():
    result = poll_waiting_orders()
    assert isinstance(result, int)


def test_retry_supplier_releases_executes_successfully():
    result = retry_supplier_releases()
    assert isinstance(result, int)
    assert result >= 0


def test_waiting_orders_polling_query_uses_skip_locked_for_postgresql():
    compiled = str(waiting_orders_polling_query().compile(dialect=postgresql.dialect())).upper()

    assert "FOR UPDATE" in compiled
    assert "SKIP LOCKED" in compiled


def test_waiting_orders_polling_query_can_disable_skip_locked_for_sqlite_tests():
    compiled = str(waiting_orders_polling_query(use_skip_locked=False)).upper()

    assert "FOR UPDATE" not in compiled
    assert "SKIP LOCKED" not in compiled

