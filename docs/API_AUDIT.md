# API Audit

Current external integration readiness is tracked in `docs/EXTERNAL_INTEGRATION_READINESS.md`.

This audit reflects the implemented API surface today. It intentionally separates implemented MVP foundations from deferred real external integrations.

## 1. Executive Summary

SMSBridge has a broad local/closed-beta API foundation:

- buyer JWT auth
- managed buyer API keys with scopes and usage visibility
- legacy buyer API key compatibility
- buyer catalog, pricing, orders, wallet transactions, and payment intents
- idempotent buyer order creation
- centralized order state transitions and order events
- wallet holds, captures, refunds, and payment-intent deposits
- supplier API-key auth
- supplier inventory, activation history, SMS push, payout requests, and transaction history
- supplier reservation callbacks, release callbacks, and release retry queue
- supplier integration contract/runbook documented in `docs/SUPPLIER_INTEGRATION_CONTRACT.md`
- payment provider contract/runbook documented in `docs/PAYMENT_PROVIDER_CONTRACT.md`
- admin supplier creation/API-key regeneration with hashed storage and one-time raw key return
- admin payment, payout, risk, reliability, logs, metrics, and ops endpoints
- request logging with request IDs and identity attribution
- health/readiness endpoints

The core is suitable for local demos and internal closed beta with mock/manual systems after RC-1 verification passed on 2026-06-27. It is not ready for real payments, real external SMS providers, or public launch.

## 2. Current Auth Modes

| Auth mode | Implemented | Notes |
|---|---:|---|
| Buyer JWT | yes | Used by browser account flows. |
| Managed buyer API key | yes | Multiple keys, labels, scopes, revoke, usage, `last_used_at`. |
| Legacy buyer API key | yes | Kept for compatibility through `users.api_key_hash`; managed keys are preferred. |
| Supplier API key | yes | Bearer supplier key, hashed in DB. |
| Admin JWT | yes | Admin role via user account. |
| Internal webhook secret | yes | Shared-secret skeleton for internal provider/payment webhook namespaces. |

Remaining auth/security gaps:

- no email verification
- no password reset or forced password rotation flow
- already-issued access tokens remain valid until expiry after logout or admin session revocation
- provider API key encryption field exists, but real secret management/provider credential flow is not production-ready
- internal webhooks do not have provider-specific signatures yet
- production-like startup rejects wildcard CORS origins, but TrustedHost/reverse-proxy hostname enforcement is still an ops/deployment responsibility

## 3. Buyer API

| Method | Path | Status | Notes |
|---|---|---|---|
| `GET` | `/api/v1/balance` | implemented | Wallet balance and held balance. |
| `GET` | `/api/v1/services` | implemented | JWT, managed key, legacy key. |
| `GET` | `/api/v1/countries` | implemented | JWT, managed key, legacy key. |
| `GET` | `/api/v1/prices` | implemented | Uses buyer schema; returns `final_price`; does not expose `provider_cost`. |
| `POST` | `/api/v1/orders` | implemented | Optional `Idempotency-Key`; transactional wrapper. |
| `GET` | `/api/v1/orders` | implemented | Own orders only. |
| `GET` | `/api/v1/orders/{public_id}` | implemented | Own order only. |
| `POST` | `/api/v1/orders/{public_id}/cancel` | implemented | Refunds hold when allowed. |
| `POST` | `/api/v1/orders/{public_id}/finish` | implemented | Captures hold and credits supplier reward when applicable. |
| `GET` | `/api/v1/wallet/transactions` | implemented | Buyer-safe wallet ledger history. |
| `POST` | `/api/v1/payment-intents` | implemented | Creates `manual_test`/allowed-provider intent; does not credit by creation alone. |
| `GET` | `/api/v1/payment-intents` | implemented | Own payment intents. |
| `GET` | `/api/v1/payment-intents/{public_id}` | implemented | Own payment intent. |
| `POST` | `/api/v1/api-keys` | implemented | JWT-only managed key creation; returns raw key once. |
| `GET` | `/api/v1/api-keys` | implemented | JWT-only managed key list. |
| `POST` | `/api/v1/api-keys/{public_id}/revoke` | implemented | Idempotent revoke. |
| `GET` | `/api/v1/api-keys/{public_id}/usage` | implemented | Owner-only usage summary. |
| `POST` | `/api/v1/api-key/regenerate` | legacy | Legacy single-key regenerate. |
| `GET` | `/api/v1/limits` | implemented | Own limits. |

Buyer API gaps:

- no unauthenticated public catalog namespace
- no buyer-safe order event/history endpoint
- no real payment provider checkout UX/API contract

## 4. Supplier API

| Method | Path | Status | Notes |
|---|---|---|---|
| `GET` | `/supplier/v1/me` | implemented | Supplier profile, balances, reward percent, status. |
| `GET` | `/supplier/v1/inventory` | implemented | Supplier-scoped inventory. |
| `POST` | `/supplier/v1/inventory/update` | implemented | Upserts count-based inventory. |
| `GET` | `/supplier/v1/activations` | implemented | Supplier-scoped activation/reservation history with SMS summary fields. |
| `POST` | `/supplier/v1/payout-requests` | implemented | Requires active supplier, minimum amount, payout method, and payout address; moves supplier balance to held balance and writes payout hold ledger. |
| `GET` | `/supplier/v1/payout-requests` | implemented | Supplier-scoped payout requests. |
| `GET` | `/supplier/v1/transactions` | implemented | Supplier-safe ledger history. |
| `POST` | `/supplier/v1/sms` | implemented | Idempotent SMS push; writes `supplier_sms` and `sms_messages`. |

Supplier API gaps:

- no supplier self-service onboarding/KYC workflow
- no exact phone inventory model
- no external payout provider execution

## 5. Admin API

Admin endpoints cover:

- users and limits
- orders and order events
- providers
- suppliers, inventory, activations, SMS, transactions
- supplier reservation config and API-key regeneration
- wallet deposits and adjustments
- order refunds
- payment intents, manual completion, and payment credit reconciliation
- supplier payout request lifecycle and reconciliation
- supplier release retries
- audit logs
- API request logs with `request_id`, identity, method, endpoint, status filters
- metrics
- ops summary
- cleanup dry-run
- risk users and manual risk actions

Remaining admin gaps:

- list pagination/filtering is uneven
- no automated reconciliation repair
- no external payout execution tooling
- no real provider sync/credential operations
- audit coverage is useful but not complete for every sensitive action

## 6. Internal APIs

| Path | Status | Notes |
|---|---|---|
| `/internal/provider-webhooks/{provider_code}` | skeleton | Authenticated, validates provider, returns accepted/not implemented; does not mutate orders. |
| `/internal/payment-webhooks/{provider}` | foundation | Authenticated, deduplicates webhook events, transitions payment intent status, credits wallet exactly once on `succeeded`. |

Internal API gaps:

- no real provider webhook processors
- no payment provider-specific signature verification
- no provider-specific event mapping
- no provider-specific checkout/session creation
- no provider-specific amount/currency validation
- no external reconciliation import

## 7. Money and Ledger State

Implemented:

- buyer wallet available/held balances
- non-negative DB constraints for buyer and supplier balances
- wallet transaction ledger for every buyer wallet movement
- idempotent hold/capture/refund paths
- idempotent payment-intent deposit crediting
- supplier reward ledger
- supplier payout hold/release/paid ledger
- supplier payout minimum amount and destination validation
- payment and payout read-only reconciliation checks

Not implemented:

- real payment providers
- real payout providers
- chargebacks/payment refunds
- automated financial reconciliation repair
- production accounting reports

## 8. Provider and SMS State

Implemented:

- local mock provider
- supplier-pool provider path
- supplier reservation callback client and integration
- supplier reservation failure policy: clear failures rollback locally; ambiguous malformed responses with a usable external reference create failed activation plus release retry
- supplier release callback with retry queue
- supplier integration contract and operator runbook
- supplier admin API key issuance and reservation config validation
- generic `sms_messages` table for supplier and external/mock SMS
- polling with skip-locked row locking where supported

Not implemented:

- real 5sim/SMS-Activate/Sms-man order adapters
- provider credential encryption/rotation flow
- provider price/stock sync jobs
- real provider webhook processing
- provider-level reconciliation

## 9. Observability and Risk

Implemented:

- health/live/ready
- request IDs
- DB API request logs
- supplier and buyer API key request attribution
- Redis rate limiting with identity/tier policies
- risk summaries and manual risk actions
- admin ops summary
- reliability center backing endpoints
- retention cleanup dry-run

Not implemented:

- external monitoring/alerting
- dashboards outside admin UI
- automatic abuse blocking
- incident/runbook maturity
- backup/restore verification

## 10. Completed Stabilization Items

| Item | Status |
|---|---|
| Hide `provider_cost` from buyer prices | DONE |
| Buyer order idempotency | DONE |
| External/mock provider wallet-hold-before-reservation flow | DONE |
| Central order state machine | DONE |
| Order events | DONE |
| Non-negative wallet/supplier DB checks | DONE |
| Redis-backed distributed rate limiting | DONE |
| Identity-aware/tier rate limit policy | DONE |
| Generic `sms_messages` storage | DONE |
| Supplier request logging | DONE |
| Request IDs and structured request completion logging foundation | DONE |
| Internal provider webhook namespace | PARTIAL, skeleton only |
| Payment intents/manual_test/admin completion | DONE for local/manual foundation |
| Payment wallet crediting from succeeded intents | DONE |
| Payment provider integration contract | DONE |
| Payment reconciliation visibility | PARTIAL, read-only |
| Supplier payout request lifecycle | PARTIAL, no external payout provider |
| Supplier manual payout policy/accounting readiness | DONE for manual/admin flow |
| Supplier payout reconciliation | PARTIAL, read-only |
| Supplier release retry queue | DONE |
| Supplier reservation timeout/ambiguous response policy | DONE for local rollback and referenced ambiguous responses |
| Supplier integration contract/operator runbook | DONE |
| Supplier admin API key issuance readiness | DONE |
| Buyer wallet transaction history | DONE |
| Managed buyer API keys/scopes/usage | DONE |
| Server-side refresh/session revocation | DONE |
| Admin user refresh session revoke-all | DONE |
| Per-login-identifier brute-force lockout | DONE |
| Admin risk monitoring/actions | PARTIAL, manual-review only |
| Operational cleanup foundation | PARTIAL |
| Production backend startup safety guards | DONE for defaults/CORS; broader deployment hardening remains |

## 11. Remaining API Gaps

Blocker before friendly buyers:

- complete true browser/mobile visual QA and record results
- ensure buyer docs clearly describe manual_test/admin completion
- verify latest purchase flow in browser
- verify auth modal/session behavior

Production/security gap before broader beta:

- tune production rate limits and monitor Redis fail-open incidents
- complete backup/restore and incident response drills
- enforce trusted host/TLS/body limits at reverse proxy or app edge

Blocker before real suppliers:

- define supplier KYC/contract/support policy
- add supplier-facing activation history UI and operational onboarding runbook
- define real external payout execution process before automating payouts
- run supplier sandbox contract signoff for reservation/release/SMS idempotency

Blocker before real payments:

- choose first real provider
- implement provider signature verification and webhook event mapping
- implement provider checkout/session creation
- implement provider amount/currency validation
- production secret management
- payment reconciliation and operator runbook
- production payment UX copy and error states
- fraud/chargeback/accounting policy

Blocker before real SMS providers:

- choose first SMS provider
- implement real adapter
- implement price/stock freshness sync
- provider credential storage/rotation
- provider cancellation/release semantics
- provider error mapping and reconciliation

## 12. Notes for Developers

- Do not expose `provider_cost` to buyer/public responses.
- Do not mutate wallet/supplier balances without ledger rows.
- Keep `manual_test` clearly local/dev/internal.
- Treat internal provider webhooks as skeleton-only until real processing is implemented.
- Keep supplier fake phone path local/dev/test only.
