# SMS Provider Contract

Draft / internal. This document defines the backend architecture and operational contract for future real external SMS activation providers such as 5sim, SMS-Activate, and Sms-man. It does not implement any real provider.

Current readiness: real SMS providers are not ready. SMSBridge currently has a local/mock provider, a supplier-pool path, placeholder real-provider adapters, polling worker infrastructure, a provider webhook skeleton, order state machine integration, wallet holds/capture/refund, and generic `sms_messages` persistence.

## 1. Current Provider Model

Core provider objects:

- `providers`: provider configuration, type, status, priority, base URL, API key field, and default markup.
- `prices`: provider cost, final buyer price, availability count, and delivery-rate metadata.
- `orders`: buyer activation orders with provider id, provider order id, phone number, status, wallet price, and provider cost.
- `sms_messages`: normalized SMS persistence for provider and supplier SMS.
- `wallet_transactions`: buyer hold/capture/refund ledger.

Provider types:

- `mock`: local deterministic test provider.
- `supplier_pool`: supplier-backed reservation path.
- `five_sim`: placeholder adapter only.
- `sms_activate`: placeholder adapter only.
- `sms_man`: placeholder adapter only.

Provider router:

- Location: `apps/backend/app/providers/router.py`
- Selects adapter by `Provider.type` or legacy provider code.
- Unknown provider type returns provider unavailable instead of crashing unpredictably.
- Candidate prices are selected only for active providers with `available_count > 0`.

Adapter interface:

- Location: `apps/backend/app/providers/base.py`
- Current methods:
  - `get_prices(service_code=None, country_iso2=None)`
  - `get_number(service_code, country_iso2, operator=None)`
  - `get_order_status(provider_order_id)`
  - `cancel_order(provider_order_id)`
  - `finish_order(provider_order_id)`

Current order flow for external/mock providers:

1. Validate service/country and candidate price.
2. Create local order in `created`.
3. Create buyer wallet hold.
4. Call provider `get_number`.
5. Store provider order id and phone number.
6. Transition `created -> waiting_sms`.
7. Poll provider for SMS.
8. On SMS, set denormalized `orders.sms_text` / `orders.sms_code`, write `sms_messages`, and transition to `sms_received`.
9. Buyer finish captures wallet hold.
10. Buyer cancel or expiry refunds wallet hold and calls provider cancel when supported.

Worker:

- `app.jobs.tasks.poll_waiting_orders`
- Selects `waiting_sms` orders.
- Uses `FOR UPDATE SKIP LOCKED` on PostgreSQL to reduce double processing by concurrent workers.
- Polling remains the only implemented external-provider SMS ingestion path.

Provider webhook skeleton:

- Endpoint: `POST /internal/provider-webhooks/{provider_code}`
- Auth: `X-Internal-Webhook-Secret`
- Validates provider exists and is active.
- Does not mutate orders yet.
- Does not store request payload.

## 2. Real Provider Adapter Contract

Each real provider adapter must normalize provider-specific behavior into the existing adapter interface. Provider-specific auth, request signing, status mapping, error parsing, timeouts, and data redaction must stay isolated inside the adapter.

### `get_prices`

Purpose:

- Fetch provider-side price/availability data.
- Normalize rows into `ProviderPrice`.

Required normalization:

- service code
- country ISO2
- operator or `None`
- provider cost
- available count
- delivery rate when available

Rules:

- `provider_cost` is internal only and must never be exposed to buyers.
- `final_price` is computed internally from provider cost and markup.
- Invalid, missing, or unsupported provider rows must be skipped or recorded safely.
- Secrets and raw provider payloads must not be logged.

### `get_number`

Purpose:

- Reserve a number with the external provider.
- Normalize success into `ProviderNumber`.

Required return fields:

- `provider_order_id`: stable external provider order/activation id.
- `phone_number`: normalized E.164-like string starting with `+`.

Rules:

- Buyer wallet hold must already exist before calling this method.
- The method must be idempotent as much as the provider supports. If the provider supports a request id/client ref, pass one derived from the local order public id in the future implementation.
- If provider reservation fails, raise a normalized provider error. Do not return partial success.
- If the provider returns a number but local persistence later fails, a cancellation/compensation path must be available before real launch.

### `get_order_status`

Purpose:

- Poll external provider order status.
- Normalize provider status into `ProviderStatus`.

Required normalized statuses for current code:

- `waiting`
- `sms_received`
- `timeout`
- `failed`

Required SMS fields on `sms_received`:

- `sms_text`: full provider SMS text when available.
- `sms_code`: parsed OTP/code when available.

Rules:

- Repeated polling of the same SMS must be safe. Current `sms_messages` persistence derives a stable message id from provider order id + text + code when the adapter does not provide a message id.
- Provider responses must be sanitized before being stored in `raw_payload`.
- Provider secret/token fields must never be stored.

### `cancel_order`

Purpose:

- Release/cancel a reserved number at the provider after buyer cancel, local expiry, or local failure requiring compensation.

Rules:

- Treat provider already-cancelled responses as success.
- Treat provider order not found according to provider semantics:
  - if provider confirms no active reservation, cancellation may be considered successful;
  - if ambiguity remains, mark for operator reconciliation.
- Cancellation failure must not create negative wallet state.
- If cancellation happens after wallet refund, failures must be visible to operators before real provider launch.

### `finish_order`

Purpose:

- Tell provider the order is completed when provider supports explicit finish/complete.

Rules:

- Treat already-completed responses as success.
- Finish failure after local wallet capture is a reconciliation issue; provider-specific policy must define retry/manual escalation before launch.
- If provider does not support finish, adapter should safely no-op only if documented for that provider.

## 3. Provider Status and Error Mapping

Real adapters must map provider-specific responses into internal errors/statuses without leaking provider internals to buyers.

Required normalized outcomes:

| Normalized outcome | Meaning | Local behavior |
|---|---|---|
| `success` / `waiting_sms` | number reserved, waiting for SMS | order transitions to `waiting_sms` |
| `sms_received` | SMS/code received | order transitions to `sms_received`, SMS persisted |
| `no_number` / `out_of_stock` | provider has no matching number | try next candidate or return no number |
| `provider_timeout` | provider request timed out | try next candidate or fail cleanly |
| `provider_unavailable` | network/5xx/provider outage | try next candidate or fail cleanly |
| `invalid_credentials` | provider auth failed | disable/degrade provider operationally; buyer sees unavailable |
| `rate_limited` | provider throttled requests | back off/degrade provider; buyer sees unavailable if no fallback |
| `provider_order_not_found` | external order id unknown | reconciliation path, no unsafe wallet mutation |
| `already_cancelled` | provider already cancelled activation | treat cancel as successful |
| `already_completed` | provider already finished activation | treat finish as successful |
| `unknown_response` | unrecognized provider body/status | do not mutate into success; record diagnostic and fail/degrade |

Buyer-facing errors should remain generic and safe, such as no number available or provider unavailable.

## 4. Timeout and Retry Policy

Required provider adapter behavior:

- Use explicit connect/read timeouts.
- Do not hang worker or order creation indefinitely.
- Do not retry non-idempotent reservation calls blindly.
- Retry only when provider semantics make retry safe or a client reference/idempotency key is used.
- Polling retries happen through the worker schedule.
- Cancellation/finish retries require provider-specific policy and operator visibility before real launch.

Reservation timeout policy:

- If provider timeout occurs before a provider order id is known, fail local reservation attempt, refund wallet hold, and try next candidate when available.
- If provider timeout occurs after a provider order id is known or might have been created, create a durable compensation/reconciliation record before real launch. This is not implemented for external SMS providers yet.

## 5. Idempotency Expectations

Order creation:

- Buyer `POST /api/v1/orders` supports `Idempotency-Key`.
- Same user + same key + same body returns same order.
- Same user + same key + different body returns conflict.

Provider reservation:

- Real adapters should pass a provider-supported idempotency/client reference when available.
- Preferred reference: local order public id or a stable `sb-order-{order.public_id}` string.
- If a provider lacks idempotent reservation, adapter implementation must document the duplicate-reservation risk and compensation procedure.

Provider polling:

- Must be safe to call repeatedly.
- Must not duplicate `sms_messages`.

Provider cancellation/finish:

- Must be idempotent from the local perspective.
- `already_cancelled` and `already_completed` should be treated as successful terminal confirmations when provider semantics allow.

## 6. Price and Stock Freshness Contract

Real provider launch requires a price/stock sync job per provider.

Required sync behavior:

- Fetch provider price/stock periodically.
- Update internal `prices.provider_cost`, `prices.final_price`, `available_count`, and quality metadata.
- Store or infer `last_sync_at` if a future schema adds it.
- Mark stale provider prices unavailable or deprioritized when freshness TTL expires.
- Do not expose provider cost to buyers.

Stale price behavior:

- Buyer catalog must show only buyer-safe `final_price`.
- Final customer price is fixed at order creation.
- If provider cost changes between catalog view and order creation, order creation should use the latest internal price row selected at purchase time.
- If provider rejects reservation because price/stock changed, fail the candidate cleanly, refund the wallet hold, and try fallback if available.

Required freshness policy before launch:

- Define TTL per provider.
- Define what admin sees when a provider has stale prices.
- Define whether stale providers are excluded from routing.
- Define alerting/runbook for repeated sync failures.

## 7. Reconciliation Contract

Real provider integration must include reconciliation visibility before launch.

Cases to detect:

- Local order exists but provider order is missing.
- Provider order exists but local order failed or was rolled back.
- Provider says completed/SMS received but local order is still `waiting_sms`.
- Local order was refunded/cancelled/expired but provider later returns SMS.
- External cancellation failed after local refund/cancel.
- Provider finish failed after local capture.
- Provider balance/expense differs from internal `provider_cost`.

Required response:

- Do not mutate wallet directly.
- Do not expose provider internals to buyers.
- Record safe diagnostic fields for admin/operator review.
- Use wallet ledger for any financial correction.
- Keep provider-specific reconciliation under adapter/provider service boundaries.

## 8. Credential and Security Requirements

Real provider credentials:

- Must not be logged.
- Must not be returned by buyer, supplier, or admin list responses.
- Must not be stored in plaintext logs or request logs.
- Must be isolated per provider adapter.
- Must support production rotation policy before launch.
- Must not be committed in `.env.example`, tests, docs, or seed data.

Before real launch:

- Decide whether `providers.api_key_encrypted` is sufficient or whether KMS/secret manager integration is required.
- Define who can view/regenerate/rotate provider credentials.
- Add provider-specific auth tests that assert secrets are not leaked.

## 9. Operator Runbook

### Provider outage

1. Check health/ops summary and recent provider error rates.
2. Disable or degrade provider in admin config if failures are sustained.
3. Confirm fallback providers remain active.
4. Tell buyers/support: "Temporary provider availability issue; no wallet funds are captured unless order completes."
5. Review failed orders and wallet refunds.

### High timeout rate

1. Check provider network/API status.
2. Reduce provider priority or disable temporarily.
3. Confirm wallet holds are refunded for failed/expired orders.
4. Check worker backlog and polling latency.
5. Escalate to provider support with sanitized request ids/order references.

### Invalid credentials

1. Disable provider immediately or mark inactive.
2. Rotate credentials through approved secret process.
3. Do not paste credentials into logs, chat, tickets, or docs.
4. Re-enable only after sandbox/live verification succeeds.

### Stale prices

1. Check last successful price sync.
2. Disable stale provider from routing if TTL exceeded.
3. Re-run sync job after provider/API recovery.
4. Confirm buyer catalog is not showing stale/unavailable stock.

### Cancellation failures

1. Confirm local wallet refund/cancel state.
2. Check provider order status externally.
3. Retry cancel only if provider semantics make it safe.
4. Escalate ambiguous live reservations to provider support.
5. Do not reverse buyer wallet refund without approved ledger policy.

### Repeated unknown responses

1. Capture sanitized response code/category, not raw secret-bearing payloads.
2. Disable/degrade provider if unknown response rate is high.
3. Add/update adapter status mapping tests before re-enabling.

### When to disable/degrade provider

Disable or deprioritize when:

- invalid credentials are detected
- timeout/unavailable rates exceed operational threshold
- price sync is stale
- unknown responses repeat
- cancellation/finish reconciliation issues accumulate
- provider violates compliance/support requirements

## 10. Required Tests Before First Real Provider

Provider adapter tests must cover:

- price sync normalization
- reservation success returns normalized provider order id and phone number
- reservation no-number/out-of-stock
- reservation timeout/unavailable
- invalid credentials
- rate limiting
- unknown response
- polling waiting status
- polling SMS received with code/text
- duplicate polling does not duplicate `sms_messages`
- cancel success
- already-cancelled cancel response
- cancel failure and reconciliation visibility
- finish success or documented no-op
- already-completed finish response
- stale price exclusion/deprioritization
- provider cost never appears in buyer responses
- wallet hold/refund/capture remains correct on provider failures
- credentials are not logged or returned

## 11. Readiness Status

Current status:

- Local/mock provider testing: ready.
- Supplier-pool provider path: mostly ready for sandbox after supplier contract signoff.
- Real external SMS providers: not ready.

Blockers before first real SMS provider:

- choose provider and integration order
- implement real adapter
- implement provider credential storage/rotation policy
- implement price/stock sync and freshness TTL
- implement provider-specific status/error mapping
- implement cancellation/finish semantics and compensation policy
- implement provider reconciliation visibility
- run provider sandbox tests
- define buyer/support messaging for provider outages and failures
