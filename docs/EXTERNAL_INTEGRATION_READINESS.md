# External Integration Readiness

This document is the current source of truth for SMSBridge readiness before involving external parties. It reflects the implemented backend/frontend state verified from code and docs, not only roadmap intent.

Execution order and go/no-go gates are tracked in `docs/EXTERNAL_ONBOARDING_ROADMAP.md`.

## 1. Readiness by External Party

| Target | Status | Summary |
|---|---|---|
| Local demo | Ready | RC-1 full backend tests, frontend build, migrations, health checks, and local E2E smoke passed on 2026-06-27. |
| Internal closed beta with manual/mock systems | Mostly ready | Core flows and admin ops surfaces exist; RC-1 build/test/smoke passed. True visual browser/mobile QA still needs a recorded pass. |
| Friendly buyer testing | Mostly ready | Buyer storefront, wallet history, manual_test deposit intent, orders, and API keys exist; funding is still manual/admin-completed. RC-1 technical checks passed; browser/mobile QA remains. |
| Real supplier onboarding | Not ready | Supplier API/cabinet foundation exists, admin supplier API key issuance is explicit, wallet hold now precedes supplier callback reservation, activation history exists, malformed ambiguous responses with external references enqueue release retry, manual payout policy is documented/enforced, and the integration contract/runbook is documented. KYC/contract policy, supplier UI polish, external payout execution, and sandbox signoff remain. |
| Real payment integration | Not ready | Payment intent/webhook/wallet-credit foundation exists and `docs/PAYMENT_PROVIDER_CONTRACT.md` defines the required provider contract, but real provider signatures, reconciliation, secrets, and UX are deferred. |
| Real SMS provider integration | Not ready | Provider skeleton and mock exist and `docs/SMS_PROVIDER_CONTRACT.md` defines the required adapter/ops contract, but real adapters, price/stock sync, credentials, error mapping, and reconciliation are deferred. |
| Public launch | Not ready | Needs legal, monitoring/alerting, production runbooks, provider/payment integrations, support, and load/security verification. Backend production runbook and session revocation exist, but operational signoff is not complete. |

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
- server-side refresh session revocation with logout/logout-all/admin target-user revoke-all
- PostgreSQL-backed login brute-force lockout
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
- real SMS provider contract/runbook in `docs/SMS_PROVIDER_CONTRACT.md`

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
- real provider contract/runbook in `docs/PAYMENT_PROVIDER_CONTRACT.md`

### Supplier cabinet/API

- supplier API-key auth
- supplier profile
- inventory list/update
- activation/reservation history
- SMS push
- payout request create/list
- supplier transaction history

### Supplier callbacks

- reservation callback client
- explicit reservation failure policy:
  - clear timeout/connection/HTTP/invalid responses fail locally, refund the buyer hold, restore inventory, and do not create activation/retry
  - malformed/non-reserved responses that still include a valid supplier activation id and phone are treated as ambiguous external reservations and enqueue release retry
- reservation config on suppliers
- release callback
- release retry queue
- supplier integration contract and operator runbook in `docs/SUPPLIER_INTEGRATION_CONTRACT.md`
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
- production backend runbook and startup safety guards

### Risk/compliance foundation

- basic risk summaries
- manual risk actions/watch/review notes
- no auto-ban or auto-blocking

### Docs/tests

- buyer, supplier, callback, local E2E, retention, and strategy docs exist.
- backend tests cover many core areas, but full latest verification still needs to be run and recorded.

## 3. Before Friendly Buyers

### Blockers

- Complete and record true visual browser QA for the storefront order flow after recent UI shell/auth changes.
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

- Define supplier onboarding/KYC/contract/support policy.
- Add supplier activation history to the supplier UI and document how suppliers should use it operationally.
- Run supplier sandbox signoff against `docs/SUPPLIER_INTEGRATION_CONTRACT.md`.
- Define real payout provider/external settlement process if payouts will move beyond manual admin mark-paid.
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
- Implement provider-specific checkout/session creation.
- Implement provider-specific amount and currency validation.
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
| Frontend buyer MVP | 78% | Storefront and account flows exist; frontend build and route availability passed in RC-1; true visual/mobile QA remains. |
| Supplier MVP | 80% | API/cabinet/callbacks/manual payout skeleton, admin API key issuance, backend activation transparency, and supplier integration/payout runbook exist; KYC, external payout execution, and supplier UI polish remain. |
| Admin/ops MVP | 80% | Broad operational UI and endpoints exist; pagination and payment/provider production runbooks missing. |
| Docs | 80% | Main docs, supplier contract/runbook, payment provider contract, and SMS provider contract are reconciled; implementation-specific provider docs remain future work. |
| Real payments | 25% | Intent/webhook/crediting base exists; provider verification absent. |
| Real SMS providers | 20% | Adapter skeletons exist; real integration absent. |
| Production launch | 35% | Good MVP base; needs integrations, legal, security, monitoring, and ops maturity. |

## 9. Top Next Tasks

| Task | Area | Priority | Complexity | Why it matters | Suggested verification |
|---|---|---|---|---|---|
| Complete browser visual QA and record results | frontend/tests | blocker | medium | RC-1 build/smoke passed, but true desktop/mobile/light/dark visual QA was not completed due browser tooling failure. | Browser pass across `/`, `/buy`, `/dashboard`, `/orders`, `/deposit`, `/api-docs`, `/supplier`, `/admin`. |
| Run supplier sandbox contract signoff | ops/tests/docs | blocker | medium | Code and runbook exist, but a real supplier must prove idempotent reservation, release, SMS, and timeout behavior before onboarding. | Execute contract checklist from `SUPPLIER_INTEGRATION_CONTRACT.md`. |
| Clarify manual_test payment UX/docs | docs/frontend | blocker | small | Friendly buyers must not think payment intent creation funds wallet. | Review `/deposit`, `API_BUYER.md`, local E2E guide. |
| Verify storefront auth/order browser flow | frontend/tests | blocker | medium | Recent shell/auth changes are central to buyer testing. | Browser smoke: select offer, login, create order. |
| Add supplier activation history to supplier UI | frontend | beta-useful | medium | Backend activation history exists; real suppliers still need it surfaced in the cabinet. | `/supplier` UI and browser smoke. |
| Run auth/session browser QA | frontend/tests | beta-useful | small | Backend logout/logout-all exists; browser token handling still needs a recorded visual/session pass. | Browser login, refresh, logout, protected-route check. |
| Choose and implement first payment provider verification | backend | blocker for real payments | large | Real payments cannot launch on shared-secret skeleton; provider-specific signature, checkout, amount/currency validation, and event mapping are required by `PAYMENT_PROVIDER_CONTRACT.md`. | Provider webhook fixture tests and reconciliation tests. |
| Choose and implement first real SMS provider adapter | backend | blocker for real SMS | large | Marketplace cannot use real external SMS stock without a provider adapter that satisfies `SMS_PROVIDER_CONTRACT.md`. | Adapter contract tests and sandbox integration. |
| Add provider price/stock sync freshness | backend/ops | beta-useful | medium | Prevents stale pricing/availability. | Sync task tests and admin visibility. |
| Write production runbook | docs/ops | blocker for launch | medium | Operators need deploy, backups, incidents, payments, supplier escalation. | Dry-run deployment checklist. |

## 10. Immediate Next 3 Tasks

1. Complete RC-2 browser visual QA and record exact results.
   - Highest remaining friendly-buyer blocker after RC-1 backend/frontend/smoke verification passed.

2. Run supplier sandbox contract signoff.
   - Highest remaining supplier operations blocker now that the contract and timeout/release runbook are documented.

3. Clarify manual_test payment behavior in buyer-facing copy/docs and verify the browser purchase/deposit flow.
   - Highest product blocker before friendly buyer testing.

## 11. Current Uncertainties

- True browser/mobile visual behavior was not verified during RC-1 because the in-app browser connector failed during setup. Route availability was checked over HTTP.
- Supplier reservation/release behavior still needs sandbox signoff with the first real supplier.
- Real payment and SMS provider choices are not decided in the repo.

## 12. BE-30 Final Backend Audit Snapshot

This snapshot separates backend readiness from UI polish, external contracts, and real third-party integrations.

| Area | Backend readiness | Notes |
|---|---|---|
| Friendly buyers with manual/mock systems | Mostly ready | Buyer auth, orders, idempotency, wallet ledger, manual_test deposits, wallet history, API keys/scopes, and rate limits exist. RC-1 backend/frontend/smoke verification passed; true browser/mobile visual QA remains before inviting buyers. |
| First real supplier sandbox | Mostly ready | Reservation callback, wallet-hold-before-reservation, release retry, activation history, admin API key issuance, config validation, supplier SMS, and manual payout accounting are implemented. Requires KYC/contract policy, supplier sandbox signoff, and external payout execution process before production onboarding. |
| Real payments | Not ready | Payment intent lifecycle and idempotent wallet crediting exist, but real provider signature verification, provider-specific webhook mapping, checkout UX, and chargeback/refund policy are not implemented. |
| Real SMS providers | Not ready | Mock/local and supplier-pool paths exist, the provider contract is documented, and the internal provider webhook namespace is skeleton-only. Real provider adapters, price/stock freshness, credential rotation, cancellation semantics, and reconciliation remain. |
| Operations for closed beta | Mostly ready | Request IDs/logs, audit logs, health, risk actions, ops summary, release retries, reconciliation, cleanup dry-run, production startup guards, and backend runbook exist. External alerting, incident drill, backup/restore verification, and accounting-grade reporting remain. |

Remaining backend blockers by severity:

- P0 before external parties: complete true browser/mobile visual QA; run supplier sandbox contract signoff; keep real payments disabled until provider verification is implemented; keep real SMS providers disabled until a real adapter and provider reconciliation are implemented.
- P1 before broader beta: provider price/stock freshness; production deployment/incident drill; external alerting; operator playbooks for repeated supplier release failures.
- P2 after beta foundation: automated reconciliation repair; exact phone inventory option; supplier self-service onboarding/API key rotation; richer accounting reports.

## 13. RC-1 Verification Record

Date: 2026-06-27

| Check | Command | Result |
|---|---|---|
| Backend image build | `docker compose build backend` | PASS |
| Backend services | `docker compose up -d postgres redis backend` | PASS |
| Alembic upgrade | `docker compose exec backend alembic upgrade head` | PASS |
| Alembic heads | `docker compose exec backend alembic heads` | PASS, single head `0022_obs_index_audit` |
| Alembic current | `docker compose exec backend alembic current` | PASS, current `0022_obs_index_audit` |
| Full backend tests | `docker compose exec backend python -m pytest app/tests` | PASS, `283 passed, 1 warning` |
| Frontend image build | `docker compose build frontend` | PASS |
| Frontend production build | `docker run --rm smsbridge-frontend npm run build` | PASS |
| Frontend service | `docker compose up -d frontend` | PASS |
| Fake supplier service | `docker compose --profile dev up -d fake-supplier` | PASS |
| Local E2E smoke | `python tools/local_e2e_smoke.py` with local Docker URLs | PASS, covered health, manual_test payment completion, supplier reservation, supplier SMS, finish, wallet ledger, supplier reward |
| Backend health endpoints | `GET /health/live`, `GET /health/ready` | PASS, live `ok`, ready database/Redis `ok` |
| Frontend route availability | HTTP checks for `/`, `/buy`, `/dashboard`, `/orders`, `/deposit`, `/api-docs`, `/supplier`, `/admin` | PASS, all returned HTTP 200 |
| Visual browser QA | in-app browser connector setup | NOT COMPLETED, connector failed before navigation; desktop/mobile/light/dark visual pass still required |

RC-1 conclusion:

- Backend release-candidate verification passed.
- Frontend build and route availability passed.
- Local manual/mock E2E smoke passed.
- True visual browser QA remains the main unrecorded friendly-buyer readiness item.

## 14. BE-31 Production Backend Safety Audit

Date: 2026-06-27

Code hardening:

- Production-like startup now rejects wildcard `CORS_ORIGINS`.
- Existing startup guards already reject default/weak `SECRET_KEY`, default `ADMIN_SEED_PASSWORD`, and empty/default `INTERNAL_WEBHOOK_SECRET`.

Documentation:

- Production backend policy is documented in `docs/PRODUCTION_BACKEND_RUNBOOK.md`.
- `.env.example` now explicitly lists `INTERNAL_WEBHOOK_SECRET` and warns against wildcard production CORS.

Auth/session conclusion:

- Server-side refresh sessions are implemented in PostgreSQL.
- Login/register create refresh sessions, refresh validates session `jti`, logout revokes the current refresh session, logout-all revokes all current-user refresh sessions, and admins can revoke all refresh sessions for a target user.
- Refresh tokens issued before BE-32 do not contain `jti` and are rejected by `/auth/refresh`.

Remaining production blockers:

- external monitoring/alerting
- backup/restore verification
- incident response/deployment runbook drill
- formal KMS/encryption-at-rest policy for real supplier/provider secrets
- real payment/provider verification and reconciliation before any real integrations

## 15. BE-32 Refresh Session Revocation

Date: 2026-06-29

Implemented:

- `refresh_sessions` table in PostgreSQL.
- Refresh JWTs include a session `jti`.
- `/auth/login` and `/auth/register` create refresh sessions.
- `/auth/refresh` rejects missing, expired, or revoked refresh sessions.
- `/auth/logout` revokes the supplied refresh session.
- `/auth/logout-all` revokes all active refresh sessions for the authenticated user.
- `/admin/users/{user_id}/sessions/revoke-all` revokes all active refresh sessions for a target user and audit-logs the action.

Compatibility note:

- Old stateless refresh tokens without `jti` are rejected after this migration.
- Access tokens remain stateless and continue to work until expiry.

## 16. BE-33 Admin User Session Controls

Date: 2026-06-29

Implemented:

- Admin-only target-user refresh session revoke-all endpoint.
- Idempotent response with newly revoked session count.
- Audit log entry for each admin revoke-all action.
- No refresh token values are stored or returned.

Limitations:

- Already-issued access tokens remain valid until their normal expiry.
- Password reset, MFA, and forced password rotation remain unimplemented.

## 17. BE-34 Login Brute-Force Protection

Date: 2026-06-29

Implemented:

- Durable `login_attempts` table keyed by SHA-256 hash of normalized login identifier.
- Configurable threshold and lock duration with `LOGIN_MAX_FAILED_ATTEMPTS` and `LOGIN_LOCKOUT_SECONDS`.
- Generic login failure response for invalid, unknown, and locked identifiers.
- Successful login resets failed-attempt state.
- Admin accounts are protected by the same policy.

Limitations:

- This is account/identifier lockout only; it does not add MFA, password reset, or IP/device anomaly detection.

## 18. BE-35 Payment Provider Contract

Date: 2026-06-29

Implemented:

- `docs/PAYMENT_PROVIDER_CONTRACT.md` documents the current internal payment model and real-provider contract.
- Real providers must implement provider-specific checkout/session creation, signature verification, event mapping, amount validation, currency validation, event deduplication, and safe diagnostics before wallet crediting.
- Operator runbook covers paid-but-not-credited, credited-but-not-succeeded, duplicate webhook, wrong amount, unknown intent, late success, refund, chargeback, and dispute cases.

Limitations:

- No real payment provider code was added.
- `manual_test` remains the only enabled payment provider.
- The generic internal webhook skeleton is not sufficient for real providers by itself.

## 19. BE-36 SMS Provider Contract

Date: 2026-06-29

Implemented:

- `docs/SMS_PROVIDER_CONTRACT.md` documents the current provider model and real SMS provider adapter contract.
- The contract covers `get_prices`, `get_number`, `get_order_status`, `cancel_order`, `finish_order`, status/error mapping, timeout/retry/idempotency policy, price/stock freshness, reconciliation, credential security, and operator runbooks.

Limitations:

- No real SMS provider code was added.
- 5sim, SMS-Activate, and Sms-man adapters remain placeholders.
- Provider webhook processing remains skeleton-only and does not mutate orders.

## 20. BE-37 External Onboarding Roadmap

Date: 2026-06-29

Implemented:

- `docs/EXTERNAL_ONBOARDING_ROADMAP.md` defines the recommended sequence: RC-2 browser QA, friendly buyer closed beta, first supplier sandbox, first real payment provider sandbox, first real SMS provider sandbox, then broader beta.
- The roadmap records entry criteria, allowed/forbidden actions, success criteria, rollback criteria, required docs, required checks, go/no-go gates, and risk register.

Limitations:

- This is a planning/readiness document only.
- It does not implement real providers, real payments, UI fixes, or production launch processes.
