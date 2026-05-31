# Callbacks / Webhooks — Draft / Internal

This document describes callback/webhook-style HTTP contracts currently implemented or planned in this repo.

Status legend:
- Implemented: present in code and used by current flows.
- Skeleton: endpoint exists but does not mutate core state yet.
- Planned: described for future work; not wired into production logic yet.

## 1. Supplier Reservation Callback (Implemented)

Direction: smsbridge -> Supplier

Configured per-supplier (admin config fields on `suppliers`):
- `reservation_enabled` (bool)
- `reservation_url` (string)
- `reservation_auth_type` (`none` or `bearer`)
- `reservation_auth_secret_encrypted` (secret string; treated as opaque)
- `reservation_timeout_seconds` (int; default 5 if missing)

### Request

Method: `POST {supplier.reservation_url}`

Headers:
- `Idempotency-Key: sb-order-{order_public_id}` (current convention)
- `Authorization: Bearer <secret>` only when `reservation_auth_type == bearer`

Body:
```json
{
  "request_id": "uuid-or-trace-id",
  "order_public_id": "ord_...",
  "service_code": "telegram",
  "country_iso2": "ID",
  "operator": null,
  "client_price": "0.2500",
  "supplier_reward": "0.1750",
  "timeout_seconds": 5
}
```

Notes:
- `client_price` and `supplier_reward` are strings in the outbound payload.
- smsbridge expects the supplier to enforce idempotency:
  - same key + same payload => same result
  - same key + different payload => `409 Conflict`

### Success response

`2xx` with JSON:
```json
{
  "status": "reserved",
  "supplier_activation_id": "sup-act-123",
  "phone_number": "+628123456789",
  "expires_at": "2026-01-01T00:00:00Z"
}
```

Validation rules (enforced by smsbridge client):
- `status` must be `"reserved"`
- `supplier_activation_id` must be a non-empty string
- `phone_number` must be a non-empty string and start with `"+"`
- `expires_at` is optional; if present must be ISO datetime

### Errors / retry behavior

Supplier responses:
- `>= 400` is treated as unavailable/error by smsbridge.

Network failures:
- Timeout / request error is treated as reservation failure.

Current behavior:
- smsbridge may fall back to another supplier/provider depending on the active routing logic.
- smsbridge does not expose supplier secrets or raw supplier error bodies to buyer clients.

## 2. Supplier Release Callback (Implemented; best-effort with retry queue)

Direction: smsbridge -> Supplier

When invoked:
- On order cancel/expire/fail for reservation-enabled suppliers.
- Release failures must not block wallet refund or order cancellation/expiration.

### Request

URL derivation:
- If `reservation_url` ends with `/reservations`, smsbridge calls the sibling `/release`.
  - Example: `https://supplier.example/v1/reservations` -> `https://supplier.example/v1/release`
- Otherwise smsbridge appends `/release` to `reservation_url`.

Method: `POST {release_url}`

Headers:
- `Idempotency-Key: sb-release-{order_public_id}`
- `Authorization: Bearer <secret>` only when `reservation_auth_type == bearer`

Body:
```json
{
  "request_id": "uuid-or-trace-id",
  "order_public_id": "ord_...",
  "supplier_activation_id": "sup-act-123",
  "phone_number": "+628123456789",
  "reason": "cancelled",
  "timestamp": "2026-01-01T00:00:00+00:00"
}
```

Success:
- Any `2xx` response is treated as success. Response body is ignored.

Failure:
- Timeouts / 4xx / 5xx are treated as release failure, but do not block order state changes or refunds.
- Failed releases are persisted in `supplier_release_retries` and retried by the Celery task `app.jobs.tasks.retry_supplier_releases`.
- Retries are capped and move to `dead` after max attempts; retry requests reuse the same idempotency key.

## 3. Internal Provider Webhook Endpoint (Skeleton)

Status: Skeleton only. Does not mutate orders yet. Polling remains the source of truth for provider SMS ingestion.

Direction: Provider system -> smsbridge (internal-only integration surface)

Endpoint:
- `POST /internal/provider-webhooks/{provider_code}`

Auth:
- Header `X-Internal-Webhook-Secret: <secret>`
- Secret comes from `INTERNAL_WEBHOOK_SECRET`
- Missing/invalid secret is rejected (`403 Forbidden`)

Behavior:
- Validates provider exists by `provider_code`
- Validates provider is `active`
- Accepts JSON payload, but does not store it and does not update orders yet
- Returns an accepted/not-implemented response:
```json
{
  "status": "accepted",
  "provider_code": "mock",
  "detail": "not_implemented"
}
```

Logging:
- Request is recorded in `ApiRequestLog` as metadata only (endpoint/method/ip/status).
- No request body is logged.
- Secret headers must never be logged.

Production safety:
- In production-like environments, startup config validation rejects empty/default `INTERNAL_WEBHOOK_SECRET`.

## 4. Internal Payment Webhook Endpoint (Foundation)

Status: Foundation only. It can transition payment intent statuses and credits wallet balance exactly once when an intent transitions to `succeeded`. Real provider signature verification is not implemented yet.

Endpoint:
- `POST /internal/payment-webhooks/{provider}`

Auth:
- Header `X-Internal-Webhook-Secret: <secret>`
- Optional `Idempotency-Key` header for caller-side replay safety.

Supported provider path values:
- `manual_test`
- `payme`
- `click`
- `crypto_usdt`

Payload shape for current skeleton:
```json
{
  "event_id": "provider-event-id",
  "payment_intent_public_id": "payment-intent-public-id",
  "status": "pending"
}
```

Current target lookup:
- `payment_intent_public_id` or `public_id`
- `provider_reference` if present

Allowed status transitions:
- `created -> pending`
- `created -> failed`
- `created -> cancelled`
- `pending -> succeeded`
- `pending -> failed`
- `pending -> cancelled`

Webhook event persistence:
- Events are stored in `payment_webhook_events`.
- Duplicate detection uses provider + external event id when present.
- If no event id exists, duplicate detection falls back to provider + deterministic payload hash.

Important:
- `succeeded` credits the buyer wallet only when the payment intent transitions into `succeeded`.
- Wallet crediting creates a `WalletTransaction` with `type = deposit` linked to the payment intent.
- Replayed duplicate events and alternate succeeded events for an already-succeeded payment intent do not credit again.
- Real provider signature verification is not implemented yet.
- Raw webhook payload is not stored.

Operational visibility:
- Admins can call `GET /admin/payment-intents/reconciliation` to see read-only counts and recent examples of payment intent / wallet credit mismatches.
- This endpoint does not mutate wallet balances or payment intent status.

## 5. Current Limitations

- Provider SMS webhooks are not implemented yet; all external provider SMS ingestion happens via polling.
- Real payment provider verification/signature validation is not implemented yet.
- Real provider-side payment reconciliation is not implemented yet.
- Supplier release callback is best-effort with a durable retry queue, but no operator escalation UI yet.
- Callback security is minimal (shared secret or bearer token). mTLS, signature verification, and replay protection are not implemented yet.
