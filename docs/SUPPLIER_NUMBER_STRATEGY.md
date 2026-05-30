# Supplier Number Strategy

Status (as of 2026-05-30):
- Reservation callback strategy (Option B) is implemented and integrated into supplier-pool order creation.
- Release callback is implemented as best-effort (failures must not block refunds/cancel/expire).
- Legacy `_fake_supplier_phone` path still exists for local/dev/test only and is blocked in production-like environments.
- A local fake supplier HTTP server exists for integration testing.

## 1. Current Supplier Flow

The current supplier pool is count-based, not phone-number-based.

Suppliers authenticate with their supplier API key and publish inventory through `POST /supplier/v1/inventory/update`. Each inventory item is stored in `supplier_inventory` with:

- `supplier_id`
- `service_code`
- `country_iso2`
- `operator`
- `available_count`
- `success_rate`
- `avg_sms_time_seconds`
- `status`
- `last_sync_at`

`app/services/suppliers.py::sync_supplier_pool_price` aggregates active supplier inventory into a synthetic `prices` row for provider `supplier_pool`. That makes supplier inventory visible to buyers through normal price discovery.

When a buyer creates an order and `services/orders.py` selects a `Price` whose provider type is `supplier_pool`, the flow calls `reserve_supplier_activation`. That function:

1. Finds an active `SupplierInventory` row with `available_count > 0`.
2. Locks candidate rows with `with_for_update`.
3. Picks one supplier inventory row by success rate, reward percent, and count.
4. Decrements `available_count`.
5. Creates a `SupplierActivation`.
6. Generates a synthetic `supplier_activation_id`.
7. Generates a fake phone number through `_fake_supplier_phone`.
8. Writes that fake number onto both `SupplierActivation.phone_number` and `Order.phone_number`.
9. Sets `Order.provider_order_id` to the synthetic supplier activation id.

Supplier SMS later arrives through `POST /supplier/v1/sms`. The payload includes `supplier_sms_id`, `phone_number`, `phone_from`, `text`, and optionally `supplier_activation_id`. The backend stores the message in `supplier_sms`, records a generic `sms_messages` row, updates the activation, and denormalizes `sms_text` / `sms_code` onto the order.

## 2. Problem

`_fake_supplier_phone` is not production-grade because the buyer receives a number that the supplier may not actually control. A real SMS activation product must reserve a real reachable phone number before showing it to the buyer.

Count-only inventory is also not enough for production because it cannot prove that a particular number exists, is available, belongs to the selected supplier, is still active, or can receive SMS for the requested service/country/operator at reservation time.

Operational risks:

- A supplier can publish `available_count=100` without having 100 usable numbers.
- The backend cannot prevent the same real number being sold twice if the supplier manages numbers outside the platform.
- Cancellations and expirations cannot reliably release a real supplier number.
- Support and reconciliation are weak because the platform has no durable record of which real number was reserved before SMS arrives.
- Fraud and compliance review are harder because phone identity exists only in supplier-side systems.

## 3. Option A: Exact Phone Inventory

In this model, suppliers upload real phone numbers before buyers order. The backend stores each number and performs exact reservation locally.

How it would work:

1. Supplier uploads or syncs individual phone numbers with service/country/operator metadata.
2. Backend stores each number in a new table, for example `supplier_phone_numbers`.
3. Buyer order creation selects and locks one available phone row.
4. Backend creates `SupplierActivation` using the exact phone number.
5. Backend marks the phone row `reserved`.
6. On SMS, completion, cancel, or expiry, backend updates the phone row status.

Required tables:

- `supplier_phone_numbers`
  - `id`
  - `supplier_id`
  - `phone_number`
  - `service_code`
  - `country_iso2`
  - `operator`
  - `status` such as `available`, `reserved`, `used`, `cooldown`, `blocked`
  - `current_activation_id`
  - `last_seen_at`
  - `reserved_at`
  - `released_at`
  - `metadata`
  - timestamps

Required endpoints:

- `POST /supplier/v1/numbers/upsert`
- `POST /supplier/v1/numbers/remove` or status update
- `GET /supplier/v1/numbers`
- Optional admin endpoints to inspect supplier number inventory.

Reservation flow:

1. Buyer order selects supplier pool price.
2. Backend locks an available `supplier_phone_numbers` row with `FOR UPDATE SKIP LOCKED`.
3. Backend creates local order and wallet hold.
4. Backend creates `SupplierActivation` linked to the phone row.
5. Backend sets order phone number from the exact phone row.
6. Backend marks phone row `reserved`.

Pros:

- Strongest platform-side control.
- No synchronous supplier dependency during buyer checkout.
- Clear audit trail for exact numbers.
- Easier duplicate prevention.
- Better admin/debug tooling.

Cons:

- Suppliers must disclose all phone numbers to the platform before sale.
- Large inventory syncs require more API and database work.
- Backend becomes responsible for number privacy and storage controls.
- Suppliers with dynamic inventory may struggle to keep platform inventory fresh.

Concurrency risks:

- Must use row-level locking or `SKIP LOCKED` during reservation.
- Must handle stale `available` rows that suppliers no longer control.
- Must make cancellation/expiry release idempotent.

Privacy/security risks:

- Platform stores real phone inventory at rest.
- Admin and logs must avoid unnecessary exposure.
- Need access controls and audit logging around phone inventory.
- Need data retention policy for used and blocked numbers.

Testing requirements:

- Concurrent reservation cannot allocate one number twice.
- Cancelled/expired orders release or retire numbers according to policy.
- Completed orders mark numbers used/cooldown.
- Supplier number upload validation rejects duplicate numbers per supplier or globally, depending on policy.
- Existing supplier SMS still links to the correct activation/order.

## 4. Option B: Reservation Callback

In this model, suppliers continue publishing count/inventory, but the backend calls the supplier at order time to reserve a real number. The supplier returns the real phone number and supplier activation id.

How it would work:

1. Supplier keeps using `POST /supplier/v1/inventory/update` to publish counts and quality metrics.
2. Supplier record stores outbound reservation configuration, such as reservation URL and auth secret.
3. Buyer order selects a supplier inventory row.
4. Backend creates local order and wallet hold.
5. Backend calls supplier reservation endpoint with service/country/operator and an idempotency key.
6. Supplier returns a real phone number and supplier activation id.
7. Backend creates `SupplierActivation` with the returned real number.
8. Backend updates `Order.phone_number` and `Order.provider_order_id`.

Required tables/fields:

- Extend `suppliers`
  - `reservation_url`
  - `reservation_auth_type`
  - `reservation_auth_secret_encrypted`
  - `reservation_timeout_seconds`
  - `reservation_enabled`
- Extend or reuse `supplier_activations`
  - keep `supplier_activation_id`
  - keep `phone_number`
  - add `reservation_request_id` or use order public id / idempotency key
  - add `reserved_at`
  - add `reservation_expires_at`
  - add `reservation_raw_response` if needed, sanitized
- Possibly extend `supplier_inventory`
  - `last_reservation_at`
  - `failed_reservation_count`
  - `last_reservation_error`

Required supplier contract:

- Supplier exposes an HTTPS reservation endpoint.
- Supplier authenticates backend calls.
- Supplier treats the provided idempotency key as idempotent.
- Supplier returns the same reservation for repeated calls with the same idempotency key and request body.
- Supplier returns clear no-inventory, timeout, and validation errors.

Request example:

```http
POST https://supplier.example.com/v1/reservations
Authorization: Bearer <supplier-reservation-secret>
Idempotency-Key: sb-order-<order_public_id>
Content-Type: application/json
```

```json
{
  "request_id": "sb-order-8e3f0f37-0f7c-4a5d-9183-7c9c8f5a9f0a",
  "order_public_id": "8e3f0f37-0f7c-4a5d-9183-7c9c8f5a9f0a",
  "service_code": "telegram",
  "country_iso2": "ID",
  "operator": null,
  "client_price": "0.5000",
  "supplier_reward": "0.3500",
  "timeout_seconds": 120
}
```

Response example:

```json
{
  "status": "reserved",
  "supplier_activation_id": "sup_abc_123",
  "phone_number": "+6281234567890",
  "expires_at": "2026-05-29T12:10:00Z"
}
```

Reservation timeout behavior:

- Backend should use a short HTTP timeout, for example 3-5 seconds.
- On timeout, backend refunds the wallet hold and tries the next eligible supplier candidate.
- If all suppliers fail or time out, return the existing no-provider/provider-unavailable style error.
- If a timeout might have reserved a number supplier-side, the idempotency key lets the backend retry or reconcile later.

Fallback behavior:

- If supplier A returns no inventory, timeout, or 5xx, mark that activation attempt failed or do not create one until a successful response.
- Try supplier B if another active inventory row matches.
- Do not decrement count permanently unless reservation succeeds.
- On repeated idempotent buyer order creation, return the original successful order and do not call suppliers again.

Pros:

- Suppliers keep control of real phone inventory.
- Platform does not need to store all available numbers before sale.
- Fits dynamic supplier systems better.
- Minimal change from current count-based inventory: counts remain useful for price/catalog availability.

Cons:

- Buyer checkout depends on supplier API latency and uptime.
- More complex failure handling.
- Requires supplier-side implementation quality and idempotency.
- Harder to guarantee count accuracy.

Concurrency risks:

- Same supplier count row may be selected concurrently; backend still needs `FOR UPDATE` around inventory selection.
- Supplier must enforce idempotent reservation and prevent duplicate number allocation.
- Backend must avoid decrementing available count before successful supplier reservation, or must restore it on failure.
- Backend must handle ambiguous timeout where supplier may have reserved but response was lost.

Security risks:

- Backend must store outbound supplier reservation secrets securely, not raw plaintext.
- Reservation URLs must be validated to avoid SSRF.
- Supplier responses must validate phone format, country, and activation id length.
- Logs must not expose secrets or excessive phone data.
- Need replay protection through idempotency and signed/authenticated requests.

Testing requirements:

- Successful reservation callback returns real phone and creates supplier activation.
- Timeout refunds wallet hold and tries fallback supplier.
- 409/idempotent retry from supplier returns the same reservation.
- Same buyer `Idempotency-Key` does not call supplier twice.
- Supplier no-inventory response tries next supplier.
- Cancel/expire calls future release endpoint or marks local activation cancelled.

## 5. Recommendation

Recommendation: choose Option B, Reservation Callback, for this project.

Reasoning:

- The current code already models supplier availability as count-based `SupplierInventory`.
- Supplier SMS delivery already uses an API callback pattern through `POST /supplier/v1/sms`.
- Moving from fake phone generation to supplier reservation callback is the smallest production-oriented step.
- It avoids storing every available supplier phone number upfront.
- It keeps supplier systems responsible for real phone ownership while the marketplace remains responsible for order, wallet, status, and SMS persistence.

Option A is stronger if the marketplace must fully control inventory, but it is a larger product and compliance commitment. It requires new number inventory management, privacy controls, admin workflows, and retention policies. For the current architecture, Option B is safer to implement incrementally.

## 6. Proposed MVP Implementation Plan

Task 8B: Add supplier reservation configuration fields. DONE

- Add nullable fields to `suppliers`: `reservation_url`, encrypted auth secret fields, `reservation_timeout_seconds`, `reservation_enabled`.
- Add admin create/update schema support.
- Do not call supplier yet.
- Add validation tests.

Task 8C: Add supplier reservation client. DONE

- Create `app/services/supplier_reservations.py`.
- Implement HTTP client wrapper with timeout, auth header, idempotency key, request/response validation.
- Add unit tests with mocked transport.
- Do not change order creation yet.

Task 8D: Integrate reservation callback and isolate `_fake_supplier_phone` as legacy/dev-only. DONE

- In `reserve_supplier_activation`, if supplier reservation is enabled, call the reservation client.
- On success, use returned phone number and supplier activation id.
- On failure, leave current fake flow available only for local/dev suppliers.
- Add wallet refund/fallback tests.

Task 8E: Add cancellation/release callback contract. DONE (best-effort only)

- Draft and implement optional supplier release endpoint call for cancelled/expired orders.
- Keep release idempotent.
- Add tests for release timeout and retry-safe behavior.

Task 8F: Add operational visibility. DONE

- Store sanitized reservation error fields on `supplier_inventory` or `supplier_activations`.
- Add admin visibility for reservation failures.
- Add metrics for reservation success rate and latency.

Task 8G: Remove fake supplier phone from production mode. DONE (blocked in production-like env; legacy allowed in local/dev/test)

- Block `_fake_supplier_phone` when `environment != local` or when supplier lacks explicit mock mode.
- Update README and deployment docs.

## 7. API Contract Draft

Backend-to-supplier reservation request:

- Method: `POST`
- Path: supplier-defined, stored as `suppliers.reservation_url`
- Auth: `Authorization: Bearer <secret>` for MVP
- Idempotency: `Idempotency-Key: sb-order-<order_public_id>` or `sb-order-<order_id>`
- Timeout: supplier-specific, default 5 seconds

Request body:

```json
{
  "request_id": "sb-order-8e3f0f37-0f7c-4a5d-9183-7c9c8f5a9f0a",
  "order_public_id": "8e3f0f37-0f7c-4a5d-9183-7c9c8f5a9f0a",
  "service_code": "telegram",
  "country_iso2": "ID",
  "operator": null,
  "client_price": "0.5000",
  "supplier_reward": "0.3500",
  "timeout_seconds": 120
}
```

Successful response:

```json
{
  "status": "reserved",
  "supplier_activation_id": "sup_abc_123",
  "phone_number": "+6281234567890",
  "expires_at": "2026-05-29T12:10:00Z"
}
```

No inventory response:

```json
{
  "status": "no_inventory",
  "message": "No matching ID telegram number"
}
```

Error handling:

- `200 reserved`: create activation and return order.
- `200 no_inventory`: try next supplier.
- `400`: treat as supplier integration error; try next supplier and record sanitized error.
- `401` / `403`: mark supplier reservation failure; alert/admin visibility.
- `409`: if idempotency conflict, do not trust response; try next supplier or fail.
- `429`: try next supplier; record throttling.
- `5xx` or timeout: refund hold for this attempt and try next supplier.

Timeout handling:

- Backend timeout should be short and explicit.
- If supplier later sends SMS for an unknown or failed activation, backend should reject or quarantine until reconciliation exists.
- Future reconciliation can retry with the same idempotency key to discover whether the supplier reserved a number.

## 8. Data Model Changes

Proposed `suppliers` additions:

- `reservation_url: string nullable`
- `reservation_auth_type: string nullable`
- `reservation_auth_secret_encrypted: string nullable`
- `reservation_timeout_seconds: integer nullable`
- `reservation_enabled: boolean default false`
- `mode: string nullable` or reuse provider/supplier status to distinguish mock vs real

Proposed `supplier_activations` additions:

- `reservation_request_id: string nullable`
- `reserved_at: datetime nullable`
- `reservation_expires_at: datetime nullable`
- `reservation_status: string nullable`
- `reservation_error_code: string nullable`
- `reservation_error_message: string nullable`

Possible `supplier_inventory` additions:

- `last_reservation_at: datetime nullable`
- `last_reservation_error: string nullable`
- `failed_reservation_count: integer default 0`

No changes are required to `orders.phone_number` or `orders.provider_order_id`; they can continue to store the returned phone number and supplier activation id.

## 9. Open Questions

- Should real supplier reservation be mandatory in production, or can selected suppliers remain in mock/fake mode?
- What auth scheme should supplier reservation callbacks use first: bearer secret, HMAC signature, mTLS, or IP allowlist plus bearer?
- Should the backend call a supplier release/cancel endpoint on buyer cancel and expiry in the first real-number release?
- What is the maximum acceptable reservation latency for buyer checkout?
- Should `available_count` be decremented before or after supplier callback success?
- Should the platform store full phone numbers forever, redact after retention, or encrypt them at rest?
- Can one real phone number be reused after completion, and if so what cooldown policy applies?
- Should duplicate phone numbers be forbidden globally across suppliers or only per supplier?
- What supplier error codes should be standardized before implementation?
- Who owns reconciliation for ambiguous timeout cases where supplier reserved a number but the backend timed out?
