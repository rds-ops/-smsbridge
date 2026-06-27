# Supplier Integration Contract

Draft/internal. This document defines the current supplier reservation and release callback contract for SMSBridge. It is intended for real supplier onboarding preparation, sandbox reviews, and operator escalation.

Current status:

- Implemented for supplier-pool orders.
- Wallet hold happens before supplier reservation callback.
- Supplier activation history exists at `GET /supplier/v1/activations`.
- Release callback failures use a durable retry queue.
- Real supplier onboarding, KYC/contract policy, and external payout execution are still not implemented.

## 1. Supplier Configuration

Reservation callbacks are configured per supplier by admins:

- `reservation_enabled`: must be `true` for production suppliers.
- `reservation_url`: supplier reservation endpoint URL.
- `reservation_auth_type`: `none` or `bearer`.
- `reservation_auth_secret_encrypted`: bearer secret value when `reservation_auth_type=bearer`.
- `reservation_timeout_seconds`: optional positive integer; default is 5 seconds.

Production/staging-like environments block the legacy fake-phone supplier path. Production suppliers must use reservation callback or a future exact-inventory flow.

## 2. Reservation Callback

Direction: SMSBridge -> supplier.

Method:

- `POST {supplier.reservation_url}`

Headers:

- `Idempotency-Key: sb-order-{order_public_id}`
- `Authorization: Bearer <secret>` only when `reservation_auth_type=bearer`

Request body:

```json
{
  "request_id": "sb-order-order-public-id",
  "order_public_id": "order-public-id",
  "service_code": "telegram",
  "country_iso2": "ID",
  "operator": null,
  "client_price": "0.5000",
  "supplier_reward": "0.3500",
  "timeout_seconds": 600
}
```

Field notes:

- `request_id`: stable request identifier for this reservation attempt.
- `order_public_id`: public order id; use this for support and idempotency diagnostics.
- `service_code`: requested service.
- `country_iso2`: ISO-2 country code.
- `operator`: nullable operator; `null` means any operator.
- `client_price`: buyer-facing price as a decimal string.
- `supplier_reward`: expected supplier reward as a decimal string.
- `timeout_seconds`: remaining activation lifetime from SMSBridge's order expiry.

Successful response:

```json
{
  "status": "reserved",
  "supplier_activation_id": "supplier-act-123",
  "phone_number": "+628123456789",
  "expires_at": "2026-06-27T12:00:00Z"
}
```

Required success fields:

- `status` must be exactly `reserved`.
- `supplier_activation_id` must be a non-empty string unique per supplier.
- `phone_number` must be a non-empty E.164-style number starting with `+`.
- `expires_at` is optional; if present, it must be an ISO datetime string.

Expected failure response:

```json
{
  "status": "no_inventory",
  "message": "No matching number is available"
}
```

Failure response rules:

- HTTP `4xx` or `5xx` is treated as supplier unavailable for that reservation attempt.
- Response bodies are not exposed to buyers.
- Do not include secrets or internal supplier diagnostics in responses.

## 3. Reservation Idempotency

Suppliers must implement idempotency for reservation callbacks.

Rules:

- Same `Idempotency-Key` and same request body must return the same reservation result.
- Same `Idempotency-Key` and different request body should return `409 Conflict`.
- If a reservation was already created, retries should return the same `supplier_activation_id` and `phone_number`.
- Idempotency records should be retained at least for the maximum activation lifetime plus the expected retry/support window.

Why this matters:

- Buyers may retry order creation due to network timeouts.
- SMSBridge may retry or operators may investigate late responses.
- Duplicate reservations with different phone numbers for the same idempotency key are not acceptable for production suppliers.

## 4. Reservation Failure Policy

SMSBridge classifies reservation callback failures into clear failures and ambiguous referenced failures.

Clear local failures:

- request timeout
- connection error
- HTTP `4xx` or `5xx`
- invalid JSON
- malformed success without a usable external reference
- response missing `supplier_activation_id`
- response missing valid `phone_number`

Behavior for clear failures:

- local order creation fails cleanly
- buyer wallet hold is refunded or rolled back
- supplier inventory count is restored
- no active supplier activation is created
- no release retry is queued
- supplier reservation failure visibility counters are updated

Ambiguous referenced failures:

- response is malformed or non-reserved, but includes both:
  - valid non-empty `supplier_activation_id`
  - valid `phone_number` starting with `+`

Behavior for ambiguous referenced failures:

- local order fails
- buyer wallet hold is refunded or rolled back
- supplier inventory count is restored
- a failed local supplier activation is retained for traceability
- a `supplier_release_retries` job is queued
- operators can inspect the failed activation and retry record

Timeout with no external reference:

- SMSBridge cannot know whether the supplier reserved a number.
- No release retry can be created because there is no activation id or phone number.
- Operators should use the runbook below for repeated or suspicious no-reference timeouts.

## 5. Release Callback

Direction: SMSBridge -> supplier.

When SMSBridge calls release:

- buyer cancels a supplier-backed order
- order expires
- order fails after a reservation-enabled supplier activation exists
- ambiguous referenced reservation failure creates a failed activation and queued release retry

Release URL derivation:

- If `reservation_url` ends with `/reservations`, SMSBridge calls sibling `/release`.
- Example: `https://supplier.example/v1/reservations` -> `https://supplier.example/v1/release`
- Otherwise, SMSBridge appends `/release` to `reservation_url`.

Method:

- `POST {release_url}`

Headers:

- `Idempotency-Key: sb-release-{order_public_id}`
- `Authorization: Bearer <secret>` only when `reservation_auth_type=bearer`

Request body:

```json
{
  "request_id": "sb-release-order-public-id",
  "order_public_id": "order-public-id",
  "supplier_activation_id": "supplier-act-123",
  "phone_number": "+628123456789",
  "reason": "cancelled",
  "timestamp": "2026-06-27T12:00:00+00:00"
}
```

Possible `reason` values:

- `cancelled`
- `expired`
- `failed`

Supplier release requirements:

- Release must be idempotent.
- Same `Idempotency-Key` and same request body should return success repeatedly.
- If the activation is already released, cancelled, expired, or unknown but safe to ignore, return `2xx`.
- Do not allocate the phone number to another buyer until the release is processed safely on supplier side.
- Do not return secrets or raw internal diagnostics.

SMSBridge behavior:

- Any `2xx` response is success.
- Timeout, connection error, `4xx`, or `5xx` is release failure.
- Release failure does not block buyer refund, cancel, expire, or fail flow.
- Failed releases are persisted in `supplier_release_retries`.
- Retry attempts use the same idempotency key.
- Retries use capped backoff and eventually become `dead`.

## 6. Supplier SMS Push

After a successful reservation, the supplier pushes SMS to:

- `POST /supplier/v1/sms`

Supplier auth:

- `Authorization: Bearer <supplier_api_key>`

Recommended body:

```json
{
  "supplier_sms_id": "message-123",
  "phone_number": "+628123456789",
  "phone_from": "Telegram",
  "text": "Your code is 12345",
  "supplier_activation_id": "supplier-act-123"
}
```

Rules:

- `supplier_sms_id` is idempotent per supplier.
- `supplier_activation_id` should be included for real suppliers.
- Phone-only matching exists as a fallback, but production suppliers should not rely on it.
- SMS text is sensitive and must not be logged unnecessarily.

## 7. Operator Runbook

### Inspect supplier reservation health

Use admin supplier/inventory views or API responses to inspect:

- `last_reservation_at`
- `last_reservation_error`
- `failed_reservation_count`
- `last_release_at`
- `last_release_error`
- `failed_release_count`

Use supplier activation history:

- Supplier-facing: `GET /supplier/v1/activations`
- Admin-facing supplier activation views, where available

Use release retry visibility:

- Admin reliability center
- `GET /admin/supplier-release-retries`

### Clear reservation failure

Examples:

- HTTP `409` for idempotency conflict
- HTTP `400` due bad request
- HTTP `503` due no inventory
- invalid JSON
- missing phone
- missing activation id

Operator handling:

1. Confirm buyer was not charged and no active order remains.
2. Confirm supplier inventory was restored.
3. Check `last_reservation_error`.
4. If the same supplier repeatedly fails, disable or degrade the supplier until fixed.
5. Ask supplier for request logs using `order_public_id` and `Idempotency-Key`.

No release retry is expected unless the response included a valid external activation id and phone.

### Ambiguous referenced reservation failure

Examples:

- `status` is not `reserved`, but response includes `supplier_activation_id` and `phone_number`.
- `status=reserved` with valid activation id and phone but invalid `expires_at`.

Operator handling:

1. Confirm local order is `failed`.
2. Confirm buyer balance/held balance is not impacted.
3. Confirm failed supplier activation exists.
4. Confirm a pending `supplier_release_retries` row exists.
5. Let the retry worker attempt release.
6. If retry reaches `dead`, contact supplier with:
   - `order_public_id`
   - `supplier_activation_id`
   - `phone_number`
   - release idempotency key `sb-release-{order_public_id}`
   - sanitized error text

Do not expose supplier raw errors or internal diagnostics to buyers.

### Timeout with no external reference

Operator handling:

1. Confirm no supplier activation id or phone was returned.
2. Confirm local order failed and buyer hold was refunded or rolled back.
3. Confirm no release retry exists; this is expected without an external reference.
4. If isolated, monitor only.
5. If repeated for the same supplier, disable or degrade the supplier and ask for supplier-side timeout logs.
6. Ask the supplier whether any reservation was created for the `Idempotency-Key`.
7. If supplier reports an external reservation, ask supplier to release it manually using their internal tools.

Supplier evidence to request:

- timestamp
- request id / idempotency key
- `order_public_id`
- returned `supplier_activation_id`, if any
- phone number, if any
- whether release was already performed

### Release retry pending

Operator handling:

1. Let automatic retry proceed while attempts remain.
2. Check whether supplier endpoint is down or auth is misconfigured.
3. Fix supplier config if needed.
4. Confirm retries use `sb-release-{order_public_id}`.
5. Do not manually refund buyers again; refund/cancel/expire already completed independently.

### Release retry dead

Operator handling:

1. Contact supplier for manual release.
2. Provide `order_public_id`, `supplier_activation_id`, `phone_number`, reason, and release idempotency key.
3. Record the escalation in internal notes or support tooling.
4. Consider disabling or degrading the supplier if repeated dead retries occur.
5. Do not expose supplier technical details to buyers.

### Disable or degrade supplier

Consider disabling/degrading when:

- repeated reservation timeouts
- repeated malformed responses
- repeated release retries become dead
- supplier cannot prove idempotent reservation/release behavior
- supplier returns different numbers for the same reservation idempotency key
- supplier SMS push is unreliable

Before re-enabling:

- supplier confirms idempotency behavior
- supplier passes sandbox reservation/release/SMS tests
- operator verifies no outstanding dead release retries need manual action

## 8. Buyer Communication Rules

Do not expose:

- supplier callback URLs
- supplier auth type or secrets
- raw supplier error bodies
- internal cost/margin fields
- supplier payout or reward data
- retry internals

Buyer-safe messaging:

- order could not be fulfilled
- no number available
- wallet hold was refunded or no charge was made
- support can investigate with order public id

## 9. Pre-Onboarding Checklist

Before enabling a real supplier:

- supplier has HTTPS reservation and release endpoints
- supplier supports bearer auth if required
- supplier implements reservation idempotency
- supplier implements release idempotency
- supplier returns `status=reserved`, `supplier_activation_id`, and `phone_number`
- supplier accepts release for already-released activations as success
- supplier can push SMS with `supplier_activation_id`
- operator has supplier API key issuance/rotation process
- operator has payout policy and support contact
- supplier has passed local/sandbox reservation, release, SMS, cancel, expire, and duplicate retry tests

Still not implemented by SMSBridge:

- supplier KYC/contract workflow
- external payout provider execution
- supplier self-service API key rotation
- exact phone inventory model
