# Retention Policy

Draft/internal policy for local and closed-beta operations.

This policy separates financial/business records from operational records. Financial and core lifecycle tables are not automatically deleted by cleanup jobs.

## Keep Indefinitely

These tables are ledger, lifecycle, or compliance-relevant and must not be deleted by automated operational cleanup:

- `wallet_transactions`: keep indefinitely.
- `supplier_transactions`: keep indefinitely.
- `orders`: keep indefinitely for now.
- `payment_intents`: keep indefinitely for now.
- `supplier_payout_requests`: keep indefinitely for now.
- `audit_logs`: long retention; no auto-delete yet.
- `order_events`: long retention; no auto-delete yet.
- `user_risk_actions`: long-term manual review history; no auto-delete yet.

## Operational Cleanup

These tables may grow quickly and can be cleaned after configurable retention windows:

- `api_request_logs`: delete after `API_REQUEST_LOG_RETENTION_DAYS`, default `90`.
- `payment_webhook_events`: delete after `PAYMENT_WEBHOOK_EVENT_RETENTION_DAYS`, default `180`.
- `supplier_release_retries`: delete only `succeeded` and `dead` rows after `SUPPLIER_RELEASE_RETRY_RETENTION_DAYS`, default `180`.

Pending supplier release retry rows are never deleted by the cleanup job.

## Deferred Cleanup

These tables are intentionally retained until product/compliance requirements are clearer:

- `sms_messages`: no auto-delete yet.
- `supplier_sms`: no auto-delete yet.

SMS retention may need stricter data-minimization rules later, but this task does not delete SMS content.

## Cleanup Controls

The cleanup service is `cleanup_expired_operational_records(db, now=None, dry_run=False)`.

Admin dry-run endpoint:

- `POST /admin/ops/cleanup/dry-run`

The admin endpoint returns counts only and does not delete rows.

Celery task:

- `app.jobs.tasks.cleanup_operational_records`

The task runs the non-dry cleanup path and is scheduled daily by Celery beat.

## Archive Strategy

No external archive storage is implemented yet. If production retention requires preserving deleted operational logs, add an export/archive task before enabling shorter retention windows.
