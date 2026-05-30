from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Order, SupplierActivation, SupplierInventory, SupplierReleaseRetry
from app.services.supplier_reservations import SupplierReleaseRequest, SupplierReservationError, release_supplier_number

logger = logging.getLogger(__name__)

RETRY_TYPE_RELEASE = "release"
RETRY_STATUS_PENDING = "pending"
RETRY_STATUS_SUCCEEDED = "succeeded"
RETRY_STATUS_DEAD = "dead"
RELEASE_RETRY_BACKOFF_SECONDS = (60, 300, 900, 3600)
MAX_RELEASE_RETRY_ATTEMPTS = len(RELEASE_RETRY_BACKOFF_SECONDS)


def sanitize_retry_error(exc: Exception | str) -> str:
    message = str(exc).strip() if not isinstance(exc, str) else exc.strip()
    if not message:
        message = exc.__class__.__name__ if not isinstance(exc, str) else "supplier_release_error"
    message = re.sub(r"Bearer\s+\S+", "Bearer [redacted]", message, flags=re.IGNORECASE)
    return message[:255]


def enqueue_release_retry(
    db: Session,
    *,
    order: Order,
    activation: SupplierActivation,
    reason: str,
    error: Exception | str,
) -> SupplierReleaseRetry:
    existing = db.scalar(
        select(SupplierReleaseRetry).where(
            SupplierReleaseRetry.supplier_activation_id == activation.id,
            SupplierReleaseRetry.retry_type == RETRY_TYPE_RELEASE,
        )
    )
    sanitized_error = sanitize_retry_error(error)
    now = datetime.now(timezone.utc)
    if existing:
        if existing.status not in {RETRY_STATUS_SUCCEEDED, RETRY_STATUS_DEAD}:
            existing.status = RETRY_STATUS_PENDING
            existing.reason = reason
            existing.last_error = sanitized_error
            if existing.next_retry_at <= now:
                existing.next_retry_at = now + timedelta(seconds=RELEASE_RETRY_BACKOFF_SECONDS[0])
        return existing

    retry = SupplierReleaseRetry(
        supplier_activation_id=activation.id,
        supplier_id=activation.supplier_id,
        order_id=order.id,
        retry_type=RETRY_TYPE_RELEASE,
        status=RETRY_STATUS_PENDING,
        reason=reason,
        attempt_count=0,
        next_retry_at=now + timedelta(seconds=RELEASE_RETRY_BACKOFF_SECONDS[0]),
        last_error=sanitized_error,
    )
    db.add(retry)
    return retry


def process_due_release_retries(db: Session, *, limit: int = 100, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    stmt = (
        select(SupplierReleaseRetry)
        .where(
            SupplierReleaseRetry.retry_type == RETRY_TYPE_RELEASE,
            SupplierReleaseRetry.status == RETRY_STATUS_PENDING,
            SupplierReleaseRetry.next_retry_at <= now,
        )
        .order_by(SupplierReleaseRetry.next_retry_at.asc(), SupplierReleaseRetry.id.asc())
        .limit(limit)
    )
    if db.get_bind().dialect.name == "postgresql":
        stmt = stmt.with_for_update(skip_locked=True)

    processed = 0
    for retry in db.scalars(stmt):
        _attempt_release_retry(db, retry, now=now)
        processed += 1
    return processed


def _attempt_release_retry(db: Session, retry: SupplierReleaseRetry, *, now: datetime) -> None:
    activation = retry.activation
    order = retry.order
    supplier = retry.supplier
    retry.last_attempt_at = now
    retry.attempt_count += 1

    if not activation or not order or not supplier or not supplier.reservation_enabled or not activation.supplier_activation_id:
        retry.status = RETRY_STATUS_DEAD
        retry.last_error = "release retry missing activation/order/supplier configuration"
        logger.warning("Supplier release retry marked dead: retry_id=%s", retry.id)
        return

    request_id = f"sb-release-{order.public_id}"
    try:
        release_supplier_number(
            supplier,
            SupplierReleaseRequest(
                request_id=request_id,
                order_public_id=order.public_id,
                supplier_activation_id=activation.supplier_activation_id,
                phone_number=activation.phone_number,
                reason=retry.reason,
                timestamp=now,
            ),
            idempotency_key=request_id,
        )
    except SupplierReservationError as exc:
        retry.last_error = sanitize_retry_error(exc)
        if retry.attempt_count >= MAX_RELEASE_RETRY_ATTEMPTS:
            retry.status = RETRY_STATUS_DEAD
            logger.warning("Supplier release retry exhausted: retry_id=%s attempts=%s", retry.id, retry.attempt_count)
        else:
            retry.status = RETRY_STATUS_PENDING
            retry.next_retry_at = now + timedelta(seconds=RELEASE_RETRY_BACKOFF_SECONDS[retry.attempt_count])
            logger.warning("Supplier release retry failed: retry_id=%s attempts=%s", retry.id, retry.attempt_count)
        _record_inventory_release_failure(db, activation, retry.last_error)
        return

    retry.status = RETRY_STATUS_SUCCEEDED
    retry.last_error = None
    _record_inventory_release_success(db, activation, now)


def _inventory_for_activation(db: Session, activation: SupplierActivation) -> SupplierInventory | None:
    return db.scalar(
        select(SupplierInventory).where(
            SupplierInventory.supplier_id == activation.supplier_id,
            SupplierInventory.service_code == activation.service_code,
            SupplierInventory.country_iso2 == activation.country_iso2,
            SupplierInventory.operator.is_(activation.operator)
            if activation.operator is None
            else SupplierInventory.operator == activation.operator,
        )
    )


def _record_inventory_release_success(db: Session, activation: SupplierActivation, now: datetime) -> None:
    inventory = _inventory_for_activation(db, activation)
    if inventory:
        inventory.last_release_at = now
        inventory.last_release_error = None


def _record_inventory_release_failure(db: Session, activation: SupplierActivation, error: str) -> None:
    inventory = _inventory_for_activation(db, activation)
    if inventory:
        inventory.failed_release_count = (inventory.failed_release_count or 0) + 1
        inventory.last_release_error = error
