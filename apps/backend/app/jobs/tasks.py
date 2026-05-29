from __future__ import annotations
import logging

from sqlalchemy import select

from app.db.session import SessionLocal
from app.jobs.celery_app import celery_app
from app.models import Order
from app.services.orders import poll_order

logger = logging.getLogger(__name__)
POLL_BATCH_LIMIT = 100


def waiting_orders_polling_query(limit: int = POLL_BATCH_LIMIT, *, use_skip_locked: bool = True):
    stmt = select(Order).where(Order.status == "waiting_sms").order_by(Order.created_at.asc()).limit(limit)
    if use_skip_locked:
        stmt = stmt.with_for_update(skip_locked=True)
    return stmt


def _supports_skip_locked(db) -> bool:
    bind = db.get_bind()
    return bind.dialect.name == "postgresql"


@celery_app.task(name="app.jobs.tasks.poll_waiting_orders")
def poll_waiting_orders() -> int:
    logger.info("Polling waiting SMS orders")
    db = SessionLocal()
    processed = 0
    try:
        orders = list(db.scalars(waiting_orders_polling_query(use_skip_locked=_supports_skip_locked(db))))
        for order in orders:
            try:
                poll_order(db, order)
                processed += 1
            except Exception:
                logger.exception("Polling failed for order %s", order.id)
        db.commit()
        logger.info("Finished polling waiting SMS orders. processed=%s", processed)
        return processed
    finally:
        db.close()
