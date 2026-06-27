# External Integration Readiness

This document is the current source of truth for SMSBridge readiness before involving external parties. It reflects the implemented backend/frontend state verified from code and docs, not only roadmap intent.

## 1. Readiness by External Party

| Target | Status | Summary |
|---|---|---|
| Local demo | Ready | Mock/manual systems, fake supplier server, manual_test payments, and local smoke script exist. Run verification before each demo. |
| Internal closed beta with manual/mock systems | Mostly ready | Core flows and admin ops surfaces exist; needs fresh full build/test/smoke pass and a few docs/copy clarifications. |
| Friendly buyer testing | Mostly ready | Buyer storefront, wallet history, manual_test deposit intent, orders, and API keys exist; funding is still manual/admin-completed. |
| Real supplier onboarding | Not ready | Supplier API/cabinet foundation exists, but onboarding policy, activation visibility, and supplier reservation/wallet compensation risk remain. |
| Real payment integration | Not ready | Payment intent/webhook/wallet-credit foundation exists, but real provider signatures, reconciliation, secrets, and UX are deferred. |
| Real SMS provider integration | Not ready | Provider skeleton and mock exist; real adapters, price/stock sync, credentials, error mapping, and reconciliation are deferred. |
| Public launch | Not ready | Needs legal, monitoring/alerting, session revocation, production runbooks, provider/payment integrations, support, and load/security verification. |

## 2. What Is Already Done

### Buyer/public marketplace

- marketplace-first home
- top navigation: Home, API, Suppliers, FAQ
- shared auth modal
- dark mode toggle
- step-based storefront flow
- persistent storefront on buyer/account pages
- FAQ and Suppliers pages

### Buyer auth/account

- JWT registration/login/refresh/current user
- buyer dashboard
- orders list/detail
- settings
- wallet balance and transaction history

### Buyer API

- services/countries/prices
- orders create/list/detail/cancel/finish
- optional `Idempotency-Key` for order creation
- managed API keys with scopes, revoke, usage
- legacy buyer API key compatibility

### Orders

- explicit transaction wrapper for buyer order creation
- state machine foundation
- order events
- external/mock provider hold-before-reservation flow
- supplier-pool reservation callback path
- polling with skip-locked row locking where supported
- generic `sms_messages` persistence

### Wallet

- hold/capture/refund
- idempotent order wallet paths
- wallet transaction ledger
- non-negative DB constraints
- buyer wallet transaction history

### Manual payments

- payment intents
- `manual_test` provider for local/dev
- admin manual completion
- internal payment webhook foundation
- idempotent wallet credit on succeeded status
- payment reconciliation visibility

### Supplier cabinet/API

- supplier API-key auth
- supplier profile
- inventory list/update
- SMS push
- payout request create/list
- supplier transaction history

### Supplier callbacks

- reservation callback client
- reservation config on suppliers
- release callback
- release retry queue
- fake supplier server for local/dev
- legacy fake phone blocked in production-like environments

### Admin

- users, orders, providers, suppliers
- supplier reservation config/visibility
- payment intents/manual completion
- supplier payout requests
- risk users/actions
- ops summary
- reliability center
- request logs with request id filtering
- audit logs and metrics

### Logs/audit/ops

- request IDs
- API request logs with user/supplier/buyer-key attribution
- health/live/ready
- Redis rate limiting with identity/tier policies
- cleanup dry-run
- retention policy

### Risk/compliance foundation

- basic risk summaries
- manual risk actions/watch/review notes
- no auto-ban or auto-blocking

### Docs/tests

- buyer, supplier, callback, local E2E, retention, and strategy docs exist.
- backend tests cover many core areas, but full latest verification still needs to be run and recorded.

## 3. Before Friendly Buyers

### Blockers

- Run full verification:
  - backend tests
  - frontend build
  - local E2E smoke script
- Verify the storefront order flow in a browser after recent UI shell/auth changes.
- Clarify buyer copy/docs around `manual_test`: creating an intent does not fund wallet; admin/manual completion or internal webhook success does.
- Verify auth modal, token refresh, logout, and false redirect behavior.
- Confirm buyer-facing prices never expose `provider_cost`.

### Nice-to-have

- mobile storefront polish
- buyer-safe order event timeline
- better account-page style consistency
- public unauthenticated catalog endpoints if product wants anonymous API browsing

## 4. Before Real Suppliers

### Blockers

- Fix or formally compensate supplier-pool reservation-before-wallet-hold risk.
- Define supplier onboarding/KYC/contract/support policy.
- Define supplier API key issuance and rotation process.
- Add supplier activation history or equivalent supplier-facing reservation transparency.
- Define timeout ambiguity handling for reservation callback:
  - timeout after supplier reserved number
  - duplicate/retry behavior
  - release retry escalation
- Define manual payout policy, minimum payout, payout method rules, and support runbook.
- Decide whether count-based callback remains the production strategy or exact inventory is required for some suppliers.

### Nice-to-have

- supplier dark-mode/table polish
- supplier callback health dashboard for suppliers
- supplier sandbox guide improvements

## 5. Before Real Payments

### Blockers

- Choose first payment provider.
- Implement provider-specific signature verification.
- Implement provider-specific webhook parsing and event ids.
- Confirm webhook replay protection and idempotent wallet crediting under provider semantics.
- Implement production secret management for payment credentials.
- Define payment reconciliation runbook.
- Define fraud, chargeback, refund, and accounting policies.
- Add production payment UX copy and error states.
- Verify regulatory/legal requirements for wallet deposits in target markets.

### Nice-to-have

- richer buyer payment history UI
- admin payment provider health dashboard
- automated reconciliation repair after manual approval

## 6. Before Real SMS Providers

### Blockers

- Choose first SMS provider and integration order.
- Implement real adapter for get prices/stock, reserve number, poll status, cancel, finish.
- Implement credential storage and rotation.
- Add provider price/stock sync freshness.
- Define polling vs webhook strategy per provider.
- Implement provider cancellation/release semantics.
- Add provider error mapping to safe internal errors.
- Add provider-level reconciliation and operational runbook.
- Confirm compliance/abuse limits and acceptable-use enforcement.

### Nice-to-have

- provider quality scoring from real completed/expired/failed orders
- provider health dashboard
- smarter provider fallback routing

## 7. Before Public Launch

### Blockers

- legal docs and terms reviewed
- privacy/acceptable-use/abuse process finalized
- production deployment/runbook
- backup/restore verification
- monitoring and alerting
- incident response/support contacts
- session/refresh-token revocation lifecycle
- rate-limit/load verification
- provider/payment/supplier support processes
- production secret management
- full security review

### Nice-to-have

- advanced fraud scoring
- analytics dashboards
- public status page
- SDKs/client libraries

## 8. Estimated Readiness

These are practical estimates, not precision metrics.

| Area | Estimate | Notes |
|---|---:|---|
| Backend core MVP | 80% | Strong local/manual foundations; real integrations deferred. |
| Frontend buyer MVP | 75% | Storefront and account flows exist; needs smoke/mobile verification. |
| Supplier MVP | 65% | API/cabinet/callbacks/payout skeleton exist; onboarding and activation transparency missing. |
| Admin/ops MVP | 80% | Broad operational UI and endpoints exist; pagination and external runbooks missing. |
| Docs | 70% | Main docs now reconciled; provider/payment-specific runbooks still needed. |
| Real payments | 25% | Intent/webhook/crediting base exists; provider verification absent. |
| Real SMS providers | 20% | Adapter skeletons exist; real integration absent. |
| Production launch | 35% | Good MVP base; needs integrations, legal, security, monitoring, and ops maturity. |

## 9. Top Next Tasks

| Task | Area | Priority | Complexity | Why it matters | Suggested verification |
|---|---|---|---|---|---|
| Run full verification and record results | tests | blocker | medium | Establishes whether current MVP actually passes after many changes. | Backend pytest, frontend build, local E2E smoke. |
| Fix supplier-pool reservation/hold ordering or strict compensation | backend | blocker | medium | Prevents real supplier number leak if wallet/DB step fails after reservation. | Targeted supplier/order wallet tests plus E2E supplier flow. |
| Clarify manual_test payment UX/docs | docs/frontend | blocker | small | Friendly buyers must not think payment intent creation funds wallet. | Review `/deposit`, `API_BUYER.md`, local E2E guide. |
| Verify storefront auth/order browser flow | frontend/tests | blocker | medium | Recent shell/auth changes are central to buyer testing. | Browser smoke: select offer, login, create order. |
| Add supplier activation history for suppliers | backend/frontend | beta-useful | medium | Real suppliers need reservation/SMS transparency. | Supplier endpoint tests and `/supplier` UI. |
| Add refresh-token/session revocation | backend | beta-useful | medium | Needed for compromised token/logout control. | Auth tests for revoke/logout. |
| Choose and implement first payment provider verification | backend | blocker for real payments | large | Real payments cannot launch on shared-secret skeleton. | Provider webhook fixture tests and reconciliation tests. |
| Choose and implement first real SMS provider adapter | backend | blocker for real SMS | large | Marketplace cannot use real external SMS stock without it. | Adapter contract tests and sandbox integration. |
| Add provider price/stock sync freshness | backend/ops | beta-useful | medium | Prevents stale pricing/availability. | Sync task tests and admin visibility. |
| Write production runbook | docs/ops | blocker for launch | medium | Operators need deploy, backups, incidents, payments, supplier escalation. | Dry-run deployment checklist. |

## 10. Immediate Next 3 Tasks

1. Run full verification and record exact results.
   - Highest leverage because docs now claim many features are implemented and need a clean current pass.

2. Fix or formally compensate supplier-pool reservation-before-wallet-hold risk.
   - Highest technical blocker before real supplier onboarding.

3. Clarify manual_test payment behavior in buyer-facing copy/docs and verify the browser purchase/deposit flow.
   - Highest product blocker before friendly buyer testing.

## 11. Current Uncertainties

- Full backend test status was not re-run during this docs reconciliation.
- Frontend build status was not re-run during this docs reconciliation.
- Browser/mobile behavior was not visually verified during this docs reconciliation.
- Supplier reservation timeout ambiguity needs design confirmation before real supplier contracts.
- Real payment and SMS provider choices are not decided in the repo.

