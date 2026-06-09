from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import ApiRequestLog, PaymentWebhookEvent, SupplierReleaseRetry


@dataclass(frozen=True)
class OperationalCleanupResult:
    api_request_logs: int
    payment_webhook_events: int
    supplier_release_retries: int
    dry_run: bool

    @property
    def total(self) -> int:
        return self.api_request_logs + self.payment_webhook_events + self.supplier_release_retries


def cleanup_expired_operational_records(
    db: Session,
    *,
    now: datetime | None = None,
    dry_run: bool = False,
) -> OperationalCleanupResult:
    now = now or datetime.now(timezone.utc)
    api_request_logs_cutoff = now - timedelta(days=max(1, settings.api_request_log_retention_days))
    payment_webhook_events_cutoff = now - timedelta(days=max(1, settings.payment_webhook_event_retention_days))
    supplier_release_retries_cutoff = now - timedelta(days=max(1, settings.supplier_release_retry_retention_days))

    api_request_logs = _count_api_request_logs(db, api_request_logs_cutoff)
    payment_webhook_events = _count_payment_webhook_events(db, payment_webhook_events_cutoff)
    supplier_release_retries = _count_supplier_release_retries(db, supplier_release_retries_cutoff)

    if not dry_run:
        db.execute(delete(ApiRequestLog).where(ApiRequestLog.created_at < api_request_logs_cutoff))
        db.execute(delete(PaymentWebhookEvent).where(PaymentWebhookEvent.created_at < payment_webhook_events_cutoff))
        db.execute(
            delete(SupplierReleaseRetry).where(
                SupplierReleaseRetry.status.in_(["succeeded", "dead"]),
                SupplierReleaseRetry.updated_at < supplier_release_retries_cutoff,
            )
        )

    return OperationalCleanupResult(
        api_request_logs=api_request_logs,
        payment_webhook_events=payment_webhook_events,
        supplier_release_retries=supplier_release_retries,
        dry_run=dry_run,
    )


def _count_api_request_logs(db: Session, cutoff: datetime) -> int:
    return int(db.scalar(select(func.count(ApiRequestLog.id)).where(ApiRequestLog.created_at < cutoff)) or 0)


def _count_payment_webhook_events(db: Session, cutoff: datetime) -> int:
    return int(
        db.scalar(select(func.count(PaymentWebhookEvent.id)).where(PaymentWebhookEvent.created_at < cutoff)) or 0
    )


def _count_supplier_release_retries(db: Session, cutoff: datetime) -> int:
    return int(
        db.scalar(
            select(func.count(SupplierReleaseRetry.id)).where(
                SupplierReleaseRetry.status.in_(["succeeded", "dead"]),
                SupplierReleaseRetry.updated_at < cutoff,
            )
        )
        or 0
    )
