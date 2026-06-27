# Architecture Map

Current external integration readiness is tracked in `docs/EXTERNAL_INTEGRATION_READINESS.md`.

This document describes the implemented architecture as of the current MVP state. It is an internal source of truth for how SMSBridge is wired today, not a future design.

## 1. System Overview

SMSBridge is a 5sim-like SMS number marketplace MVP.

Main roles:

- `buyer`: creates an account, funds a wallet, buys temporary numbers, waits for SMS, cancels or finishes orders, and can use JWT, managed API keys, or a legacy API key.
- `supplier`: marketplace partner authenticated with a supplier API key. Suppliers manage count-based inventory, receive reservation callbacks if enabled, push SMS, request payouts, and view their transaction history.
- `admin`: internal operator for users, orders, providers, suppliers, manual funding, payout review, risk review, logs, reconciliation, and operational visibility.
- `provider`: external SMS activation source or local mock provider. Real provider adapters are placeholders except the local mock and supplier-pool path.
- `worker`: Celery process for polling waiting orders, retrying supplier releases, and operational cleanup.

## 2. Main Components

### Frontend

- Location: `apps/frontend`
- Framework: Next.js App Router.
- Primary shell: marketplace-first storefront rendered by `apps/frontend/components/buyer/SmsMarketplace.tsx`.
- Main public/buyer routes:
  - `/`
  - `/buy`
  - `/faq`
  - `/suppliers`
  - `/api-docs`
  - `/dashboard`
  - `/orders`
  - `/orders/{public_id}`
  - `/deposit`
  - `/settings`
- Supplier cabinet:
  - `/supplier`
- Admin console:
  - `/admin`
- API clients:
  - `apps/frontend/lib/client/api.ts`
  - `apps/frontend/lib/admin/api.ts`
  - `apps/frontend/lib/supplier/api.ts`
  - `apps/frontend/lib/shared/api.ts`

Implemented UI foundation:

- top navigation with Home, API, Suppliers, FAQ
- account dropdown with Orders, Add funds, Settings, Supplier cabinet, Admin, Logout
- shared auth modal
- dark mode toggle
- local shadcn/ui-compatible primitives
- persistent marketplace storefront on public/buyer account pages

### Backend

- Location: `apps/backend/app`
- Framework: FastAPI.
- Entrypoint: `app/main.py`
- Routers:
  - `app/api/auth.py`
  - `app/api/api_v1.py`
  - `app/api/supplier.py`
  - `app/api/admin.py`
  - `app/api/internal_provider_webhooks.py`
  - `app/api/internal_payment_webhooks.py`
- Core services:
  - `app/services/orders.py`
  - `app/services/order_state.py`
  - `app/services/wallet.py`
  - `app/services/payment_intents.py`
  - `app/services/suppliers.py`
  - `app/services/supplier_reservations.py`
  - `app/services/rate_limit.py`
  - `app/services/risk.py`
  - `app/services/ops.py`
  - `app/services/cleanup.py`
- Models:
  - `app/models/entities.py`
- Provider adapters:
  - `app/providers/mock.py`
  - `app/providers/supplier_pool.py`
  - `app/providers/five_sim.py`
  - `app/providers/sms_activate.py`
  - `app/providers/sms_man.py`
  - `app/providers/router.py`

Real provider adapters for 5sim, SMS-Activate, and Sms-man are intentionally deferred and remain incomplete placeholders.

### PostgreSQL

PostgreSQL stores all durable business state:

- users, wallets, wallet transactions
- buyer API keys
- orders and order events
- prices and provider rows
- suppliers, inventory, activations, SMS, transactions, payout requests
- payment intents and payment webhook events
- idempotency keys
- API request logs, audit logs, risk actions, cleanup/retry state

Important database protections already implemented:

- non-negative checks for wallet balance and held balance
- non-negative checks for supplier balance and held balance
- provider type/status checks
- payment intent status/amount checks
- supplier payout status/amount checks
- normalized nullable-operator uniqueness for prices and supplier inventory
- unique wallet credit linkage by `wallet_transactions.payment_intent_id`

### Redis

Redis is used for:

- Celery broker/backend
- distributed fixed-window rate limit counters

Rate limiting is identity-aware for:

- managed buyer API key
- authenticated user/JWT
- legacy buyer API key via user bucket
- supplier
- IP fallback

Redis is not used for durable money, orders, idempotency, or reconciliation state.

### Celery

Celery worker tasks include:

- polling waiting external/mock provider orders
- retrying failed supplier release callbacks
- cleanup of expired operational records

Polling uses row-locking with `FOR UPDATE SKIP LOCKED` where supported to reduce double-processing by concurrent workers.

## 3. Buyer Flow

### Catalog and prices

Buyer API endpoints:

- `GET /api/v1/services`
- `GET /api/v1/countries`
- `GET /api/v1/prices`

Auth modes:

- buyer JWT
- managed buyer API key with matching scope
- legacy buyer API key

`/api/v1/prices` returns `final_price` and does not expose `provider_cost`.

Separate unauthenticated public catalog endpoints are not implemented. The frontend can show the storefront and then gates purchase/auth behavior through the shared auth modal.

### Order creation

Endpoint:

- `POST /api/v1/orders`

Implemented behavior:

- optional `Idempotency-Key`
- explicit transactional wrapper
- buyer limits
- wallet hold creation
- order status transition through `order_state.transition_order`
- order event history
- supplier-pool and external/mock provider paths

External/mock provider path:

1. Create local order in `created`.
2. Create wallet hold.
3. Call provider `get_number`.
4. Attach provider order id and phone.
5. Transition `created -> waiting_sms`.
6. If provider reservation fails after hold, refund the hold and mark failure.

Supplier-pool path:

1. Create local order in `created`.
2. Create buyer wallet hold.
3. Select supplier inventory with row lock.
4. Decrement supplier inventory.
5. If `reservation_enabled=true`, call supplier reservation callback and store returned real phone and supplier activation id.
6. If `reservation_enabled=false`, use legacy fake phone only in local/dev/test; production-like environments block this path.
7. Transition to `waiting_sms`.
8. If supplier reservation is unavailable after the hold, refund the hold, mark the local attempt failed, restore inventory, and continue/fail cleanly.

Known risk:

- Supplier-pool reservation no longer happens before wallet hold. Remaining real-supplier risks are callback timeout ambiguity, supplier onboarding/contract policy, supplier-facing activation visibility, and operational escalation for repeated release failures.

### Order lifecycle

Statuses:

- `created`
- `waiting_sms`
- `sms_received`
- `completed`
- `cancelled`
- `expired`
- `failed`
- `refunded`

Centralized module:

- `apps/backend/app/services/order_state.py`

Transition history:

- `order_events`
- admin endpoint: `GET /admin/orders/{order_id}/events`

Buyer actions:

- `POST /api/v1/orders/{public_id}/cancel`
- `POST /api/v1/orders/{public_id}/finish`

Cancel/expire refund wallet holds. Finish captures wallet holds and credits supplier rewards for supplier-backed orders.

## 4. SMS Flow

### External/mock provider polling

Worker polls `waiting_sms` orders. If provider returns SMS:

- `orders.sms_text` and `orders.sms_code` are updated for compatibility.
- generic `sms_messages` row is written idempotently.
- order transitions to `sms_received`.

Provider webhook namespace exists:

- `POST /internal/provider-webhooks/{provider_code}`

It is skeleton-only. It validates shared-secret auth and provider status, but does not process real provider webhook payloads.

### Supplier SMS push

Endpoint:

- `POST /supplier/v1/sms`

Behavior:

- supplier API key auth
- idempotent by supplier SMS id
- creates `supplier_sms`
- creates generic `sms_messages`
- updates supplier activation and linked order
- preserves denormalized order SMS fields

If activation id is missing, the backend can fall back to matching the latest active supplier activation by supplier and phone number. This is useful locally, but real supplier integrations should prefer explicit activation ids.

## 5. Money and Accounting

### Buyer wallet

Implemented:

- wallet balance and held balance
- admin manual deposit and adjustment
- order hold, capture, refund
- idempotent hold/capture/refund per order
- buyer wallet transaction history at `GET /api/v1/wallet/transactions`
- DB-level non-negative balance constraints

Every wallet movement must create a `WalletTransaction`.

### Payment intents

Implemented foundation:

- buyer create/list/fetch payment intents
- optional `Idempotency-Key`
- admin list/detail
- admin manual completion for `manual_test`
- internal payment webhook skeleton
- payment webhook event deduplication
- status transitions
- wallet credit exactly once when a payment intent transitions to `succeeded`
- reconciliation visibility for succeeded intent without wallet credit and linked wallet credit for non-succeeded intent

Not implemented:

- real Payme/Click/crypto/provider verification
- provider-specific signatures
- provider-specific webhook parsing
- chargeback/refund lifecycle
- real payment provider UX beyond local/manual test flow

### Supplier rewards and payouts

Implemented:

- supplier reward is credited when a supplier-backed order is completed
- supplier transaction ledger
- supplier payout request creation
- payout hold moves supplier balance to held balance
- admin approve/reject/mark-paid
- payout release and paid ledger entries
- payout reconciliation visibility

Not implemented:

- external payout provider execution
- supplier KYC/payment-account verification
- automated payout reconciliation with external payment rails

## 6. Supplier Flow

Supplier API endpoints:

- `GET /supplier/v1/me`
- `GET /supplier/v1/inventory`
- `POST /supplier/v1/inventory/update`
- `POST /supplier/v1/payout-requests`
- `GET /supplier/v1/payout-requests`
- `GET /supplier/v1/transactions`
- `POST /supplier/v1/sms`

Supplier reservation callback:

- Configured on supplier records through admin fields:
  - `reservation_enabled`
  - `reservation_url`
  - `reservation_auth_type`
  - `reservation_auth_secret_encrypted`
  - `reservation_timeout_seconds`
- Standalone client validates reservation responses.
- Reservation-enabled suppliers must return a real phone number and supplier activation id.
- Release callback is best-effort and failed releases are persisted to `supplier_release_retries` for retry.

Legacy fake supplier phone:

- local/dev/test fallback only
- blocked in production-like environments
- not suitable for real supplier onboarding

## 7. Admin Flow

Admin backend coverage includes:

- users and user limits
- orders and order events
- providers
- suppliers, inventory, activations, SMS, transactions
- supplier reservation configuration
- wallet deposit/adjustment
- order refund
- payment intents, manual completion, reconciliation
- supplier payout requests and reconciliation
- supplier release retries
- audit logs
- API request logs with request id and identity filters
- metrics
- ops summary
- operational cleanup dry-run
- risk users and manual risk actions

Admin UI coverage includes:

- metrics/users/orders/providers/suppliers
- ops summary
- risk users/actions
- payment intents/manual completion
- supplier payout requests
- reliability center
- request logs with request id filtering
- supplier reservation config and visibility fields

## 8. Observability, Risk, and Cleanup

Implemented:

- request id middleware with `X-Request-ID`
- API request logging with `request_id`, `user_id`, `supplier_id`, and `buyer_api_key_id`
- Redis fail-open rate limiting
- health endpoints:
  - `GET /health`
  - `GET /health/live`
  - `GET /health/ready`
- admin ops summary
- read-only payment and payout reconciliation
- supplier release retry visibility
- basic risk summaries and manual risk actions
- retention policy document
- cleanup helper/task for selected operational rows

Not implemented:

- external metrics platform
- alerting
- Sentry/Prometheus/Grafana dashboards
- automatic fraud blocking
- automatic reconciliation repair

## 9. Current Database Map

| Table | Purpose | Current state |
|---|---|---|
| `users` | buyer/admin accounts | JWT auth, legacy API key compatibility, status/tier fields. No session revocation table. |
| `buyer_api_keys` | managed buyer API keys | multiple keys, scopes, revoke, usage attribution. |
| `wallets` | buyer balances | non-negative DB checks. |
| `wallet_transactions` | buyer ledger | hold/capture/refund/deposit/adjustment/payment intent credit. |
| `payment_intents` | deposit intent lifecycle | manual_test and internal webhook skeleton; real providers deferred. |
| `payment_webhook_events` | webhook deduplication | status tracking; no provider-specific signature validation. |
| `providers` | provider config | type/status validation; real adapters mostly placeholders. |
| `prices` | provider/customer prices | buyer schema hides provider cost; nullable operator uniqueness normalized. |
| `orders` | buyer activations | state machine, events, idempotency, wallet linkage. |
| `order_events` | order transition history | admin-visible. |
| `sms_messages` | normalized SMS storage | supplier and external/mock provider paths write here. |
| `suppliers` | supplier accounts/balances/config | reservation config and visibility fields. |
| `supplier_inventory` | count-based supplier stock | row-locked reservation, normalized operator uniqueness. |
| `supplier_activations` | supplier reservation/order mapping | real callback ids/phones for reservation-enabled suppliers. |
| `supplier_sms` | supplier SMS idempotency/source table | also mirrored to `sms_messages`. |
| `supplier_transactions` | supplier ledger | rewards, payout hold/release/paid, adjustments. |
| `supplier_payout_requests` | supplier payout lifecycle | request/approve/reject/paid skeleton, no external payout provider. |
| `supplier_release_retries` | release callback retry queue | capped retries and dead-letter state. |
| `api_request_logs` | request logging | request_id and identity attribution. |
| `audit_logs` | admin/system audit | partial coverage. |
| `user_risk_actions` | manual risk review history | admin-only. |

## 10. API Map

| Namespace | Role | Current state |
|---|---|---|
| `/auth` | public/user | register, login, refresh, current user. No refresh token revocation table. |
| `/api/v1` | buyer/API key | catalog, prices, orders, wallet, payment intents, limits, managed API keys. |
| `/supplier/v1` | supplier | profile, inventory, payout requests, transactions, SMS push. |
| `/admin` | admin | broad operations/admin API. |
| `/internal/provider-webhooks` | internal | authenticated provider webhook skeleton only. |
| `/internal/payment-webhooks` | internal | authenticated payment webhook foundation; credits wallet on succeeded status. |
| `/health` | public ops | live/ready checks. |

## 11. Mock, Manual, Real, Deferred

Real today:

- buyer account/order/wallet ledger foundation
- supplier API-key cabinet/API
- supplier reservation callback foundation
- supplier SMS push path
- manual/admin operational flows
- payment intent lifecycle and idempotent wallet crediting
- request logging, request IDs, risk and reconciliation visibility

Mock/manual/local today:

- `mock` provider
- `manual_test` payment provider
- fake supplier server for local integration testing
- admin manual payment completion
- admin mark-paid supplier payout

Deferred:

- real external SMS provider adapters
- real external payment provider verification and payment UX
- real external supplier payout execution
- provider webhook processing
- provider price/stock sync freshness
- formal legal/KYC/support/public launch processes

## 12. Main Remaining Architecture Risks

1. Supplier callback timeout ambiguity and supplier onboarding controls still need to be finalized before real suppliers.
2. Real provider adapters are placeholders and need credential, sync, error mapping, cancellation, and reconciliation design.
3. Payment webhooks use a shared internal secret skeleton; real provider signatures and provider-specific event handling are not implemented.
4. Refresh tokens are stateless; logout/session revocation is incomplete.
5. Admin and supplier list pagination/filtering is still uneven.
6. Risk monitoring is read-only/manual-review only; no automated abuse prevention.
7. Metrics are useful for ops, but not production accounting.
