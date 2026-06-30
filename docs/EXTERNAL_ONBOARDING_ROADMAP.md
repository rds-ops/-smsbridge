# External Onboarding Roadmap

Draft / internal. This is the backend-first execution roadmap for moving SMSBridge from local/manual readiness toward external buyers, suppliers, payment providers, and SMS providers.

Source documents:

- `docs/EXTERNAL_INTEGRATION_READINESS.md`
- `docs/API_AUDIT.md`
- `docs/ARCHITECTURE_MAP.md`
- `docs/SUPPLIER_INTEGRATION_CONTRACT.md`
- `docs/PAYMENT_PROVIDER_CONTRACT.md`
- `docs/SMS_PROVIDER_CONTRACT.md`
- `docs/PRODUCTION_BACKEND_RUNBOOK.md`
- `docs/UI_READINESS_AUDIT.md`

## 1. Current State Snapshot

| Area | Status | Snapshot |
|---|---|---|
| Backend core | Internal phase complete with P1/P2 follow-ups | BE-38 found no P0 backend architecture blocker to moving into frontend completion/UI freeze. RC-1 passed backend build, migrations, full tests, health checks, and local E2E smoke. Wallet ledger, order lifecycle, idempotency, state transitions, request logs, rate limits, and auth hardening are implemented. |
| Frontend | UI Freeze Candidate | Marketplace shell, buyer dashboard, orders, deposit, API keys, supplier cabinet, and admin ops surfaces exist. RC-2 browser/mobile/light/dark QA passed after small responsive fixes. |
| Buyer readiness | Mostly ready for friendly buyers with manual/mock systems | Buyer auth, API keys/scopes, orders, wallet history, manual_test deposit intents, local E2E smoke, and RC-2 browser QA exist. Real payment UX is not implemented. |
| Supplier readiness | Sandbox-ready only after business signoff | Supplier API, public application/admin review foundation, reservation callback, release retry, activation history API/UI, payout requests, transactions, and integration contract exist. KYC/contract policy and sandbox signoff remain. |
| Payment readiness | Manual/local only | `manual_test`, payment intents, admin completion, internal webhook foundation, idempotent wallet credit, and reconciliation visibility exist. Real provider checkout, signatures, amount/currency validation, and dispute policy are not implemented. |
| SMS provider readiness | Mock/local only | Mock provider, supplier-pool path, polling worker, webhook skeleton, and SMS provider contract exist. Real adapters, credential rotation, price/stock freshness, and reconciliation are not implemented. |
| Operations readiness | Closed-beta foundation | Health endpoints, request IDs, request logs, audit logs, ops summary, risk actions, cleanup dry-run, release retries, and runbooks exist. External alerting, backup/restore drill, incident drill, and accounting-grade reporting remain. |

Backend go/no-go after BE-38:

- Go for UI freeze candidate based on RC-2 browser QA.
- Go for friendly-buyer closed beta planning with mock/manual systems after operator/support signoff.
- No-go for real payment processing until provider-specific payment integration work is implemented and verified.
- No-go for real SMS providers until real adapters, price/stock freshness, cancellation semantics, and reconciliation are implemented and verified.
- No-go for production supplier onboarding until business/KYC/contract/sandbox signoff is complete.

## 2. Recommended Order

1. Phase B frontend security/ops polish after RC-2.
2. Friendly buyer closed beta with mock/manual systems.
3. First supplier sandbox.
4. First real payment provider sandbox.
5. First real SMS provider sandbox.
6. Broader beta.

Do not reorder real payments or real SMS providers ahead of RC-2/friendly-buyer validation unless there is a specific business decision and a new risk review.

## 3. Stage Plans

### Stage 1: RC-2 Browser Visual QA / UI Freeze

Status: passed as UI Freeze Candidate on 2026-06-29. Detailed route/theme/viewport results are recorded in `docs/UI_READINESS_AUDIT.md`.

Entry criteria:

- RC-1 technical verification remains valid or is rerun if backend/frontend changed.
- Frontend build passes.
- Local E2E smoke passes.
- No active P0 backend integrity bugs.

Allowed actions:

- Browser QA for `/`, `/buy`, `/dashboard`, `/orders`, `/deposit`, `/api-docs`, `/supplier`, `/admin`.
- Light/dark and desktop/mobile checks.
- Tiny visual or copy fixes found during QA.
- Update `docs/UI_READINESS_AUDIT.md` and `docs/EXTERNAL_INTEGRATION_READINESS.md` with exact results.

Forbidden actions:

- No new backend features.
- No real payment provider work.
- No real SMS provider work.
- No broad UI redesign.
- No endless polish beyond blocking QA issues.

Success criteria:

- Browser QA record exists.
- Storefront order flow works visually.
- Auth modal/login/logout/protected-route behavior is verified.
- Deposit page clearly says `manual_test` does not fund wallet without admin/manual completion.
- Mobile layout has no blocking overlap or unreadable states.

Rollback criteria:

- Revert only the specific UI/copy fix that causes a build or flow regression.
- If a backend regression appears, stop RC-2 and create a focused backend bug task.

Required docs/runbook updates:

- `docs/UI_READINESS_AUDIT.md`
- `docs/EXTERNAL_INTEGRATION_READINESS.md`

Required tests/checks:

- `docker compose build frontend`
- `docker run --rm smsbridge-frontend npm run build`
- local E2E smoke if flow-affecting UI changed
- manual browser checklist

### Stage 2: Friendly Buyer Closed Beta With Mock/Manual Systems

Entry criteria:

- Stage 1 passed.
- Buyer-facing copy clearly describes manual funding.
- Admin manual_test completion process is documented for operators.
- Support/feedback channel exists.
- Real payments and real SMS providers remain disabled.

Allowed actions:

- Invite a small trusted buyer group.
- Use mock provider or supplier-pool sandbox/local flows only.
- Use `manual_test` payment intents and admin manual completion only.
- Monitor request logs, risk summaries, wallet transactions, payment intents, orders, and ops summary.
- Admin may manually refund/cancel according to existing policy.

Forbidden actions:

- No public launch.
- No real payment provider.
- No real external SMS provider.
- No production supplier onboarding.
- No direct wallet balance edits without ledger.
- No promises of production payment/SMS availability.

Success criteria:

- Buyers can register/login, create payment intent, receive admin-completed wallet credit, create order, cancel/finish order, and view wallet transactions.
- No provider_cost exposure.
- No stuck wallet holds in normal flows.
- Request logs and request IDs are usable for support.
- Risk actions can be recorded manually.

Rollback criteria:

- Pause buyer invites if wallet ledger inconsistency, auth/session regression, or repeated order creation failures occur.
- Disable affected provider/supplier path if reservations or SMS flows become unreliable.
- Revoke sessions/API keys for compromised or abusive accounts.

Required docs/runbook updates:

- `docs/API_BUYER.md`
- `docs/LOCAL_E2E_TESTING.md`
- `docs/EXTERNAL_INTEGRATION_READINESS.md`
- operator notes in `docs/PRODUCTION_BACKEND_RUNBOOK.md` if incidents occur

Required tests/checks:

- backend full suite if backend changed
- local E2E smoke
- buyer browser flow
- admin manual completion verification
- health/ready checks

### Stage 3: First Supplier Sandbox

Entry criteria:

- Stage 1 passed.
- Supplier candidate has business/KYC/contract approval for sandbox.
- Supplier candidate submitted the Supplier Center application or has an equivalent approved internal review record.
- Supplier has reviewed `docs/SUPPLIER_INTEGRATION_CONTRACT.md`.
- Admin creates supplier as `pending`, configures reservation callback, and issues API key through secure channel.
- Supplier activation history API/UI is available for sandbox visibility.

Allowed actions:

- Run supplier reservation callback sandbox tests.
- Run supplier release callback idempotency tests.
- Run supplier SMS push tests.
- Use limited inventory and test services/countries.
- Keep supplier status `pending` until sandbox signoff; move to `active` only for controlled sandbox routing.
- Use manual payout request flow without external payout provider execution.

Forbidden actions:

- No production supplier traffic before sandbox signoff.
- No legacy fake supplier phone in production/staging.
- No supplier with `reservation_enabled=false` for production-like routing.
- No external payout automation.
- No raw supplier API keys or reservation secrets in logs/tickets.

Success criteria:

- Same reservation idempotency key + same body returns same activation/phone.
- Same idempotency key + different body conflicts.
- Reservation success returns valid `supplier_activation_id` and `phone_number`.
- Timeout/clear failure rolls back locally and restores inventory/hold.
- Ambiguous referenced failure enqueues release retry.
- Release callback is idempotent.
- SMS push links to correct activation/order and moves order to `sms_received`.
- Supplier payout request/ledger flow works manually.

Rollback criteria:

- Set supplier `status=blocked` or `pending`.
- Disable `reservation_enabled` only outside production routing or remove provider route.
- Clear/restore test inventory.
- Revoke supplier API key if compromised.
- Escalate release retry dead-letter cases manually.

Required docs/runbook updates:

- `docs/SUPPLIER_INTEGRATION_CONTRACT.md`
- `docs/API_SUPPLIER.md`
- `docs/EXTERNAL_INTEGRATION_READINESS.md`
- supplier-specific sandbox checklist/notes

Required tests/checks:

- supplier reservation contract checklist
- supplier SMS push flow
- release retry visibility
- supplier payout request/manual ledger check
- targeted backend supplier tests if code changes

### Stage 4: First Real Payment Provider Sandbox

Entry criteria:

- Stage 1 and friendly-buyer manual flows are stable.
- First provider is selected.
- Provider implementation plan follows `docs/PAYMENT_PROVIDER_CONTRACT.md`.
- Production/sandbox credentials storage policy is approved.
- Legal/accounting policy for wallet deposits, refunds, disputes, and chargebacks is drafted.

Allowed actions:

- Implement provider-specific checkout/session creation in sandbox mode.
- Implement provider-specific webhook signature verification.
- Implement provider-specific status mapping, amount validation, currency validation, and event deduplication.
- Run sandbox webhooks and reconciliation drills.
- Keep provider disabled for normal buyers until sandbox signoff.

Forbidden actions:

- No real money crediting from unsigned/generic shared-secret webhook.
- No wallet credit without amount/currency validation.
- No production provider credentials in `.env.example`, docs, logs, or tickets.
- No chargeback/refund promises without policy.
- No public payment UI launch before sandbox signoff.

Success criteria:

- Valid signed webhook transitions intent correctly.
- Wrong signature is rejected.
- Wrong amount/currency does not credit wallet.
- Duplicate success does not double-credit wallet.
- Unknown intent does not credit wallet.
- Wallet credit remains atomic with payment intent success.
- Admin reconciliation shows clean state after happy path.

Rollback criteria:

- Disable provider in config/allowlist.
- Stop checkout/session creation.
- Keep manual_test available for local/manual flows.
- Investigate any wallet/payment mismatch through reconciliation; do not direct-edit wallet balances.

Required docs/runbook updates:

- `docs/PAYMENT_PROVIDER_CONTRACT.md`
- `docs/API_CALLBACKS.md`
- `docs/API_BUYER.md`
- `docs/EXTERNAL_INTEGRATION_READINESS.md`
- provider-specific sandbox runbook

Required tests/checks:

- provider fixture tests
- payment webhook tests
- wallet transaction tests
- reconciliation tests
- sandbox signed webhook replay tests

### Stage 5: First Real SMS Provider Sandbox

Entry criteria:

- Stage 1 passed.
- First SMS provider is selected.
- Provider implementation plan follows `docs/SMS_PROVIDER_CONTRACT.md`.
- Credential storage/rotation policy is approved.
- Provider compliance/acceptable-use constraints are understood.

Allowed actions:

- Implement provider adapter in sandbox/test mode.
- Implement price/stock sync and freshness TTL.
- Implement provider status/error mapping.
- Implement reservation, polling, cancellation, and finish semantics.
- Add reconciliation visibility for provider mismatches.
- Keep provider disabled for normal buyers until sandbox signoff.

Forbidden actions:

- No production buyer routing to placeholder adapters.
- No stale provider prices in buyer routing.
- No provider credentials in logs/responses/docs.
- No buyer exposure of `provider_cost`.
- No webhook-based order mutation until real provider webhook processing is implemented and verified.

Success criteria:

- Price sync normalizes provider prices/stock.
- Reservation returns normalized provider order id and phone.
- Wallet hold exists before reservation.
- SMS polling transitions order to `sms_received` and records `sms_messages` idempotently.
- Cancel/expire refunds wallet and handles provider cancel semantics.
- Finish captures wallet and handles provider finish semantics.
- Provider errors map to safe internal errors.
- Reconciliation cases are visible to operators.

Rollback criteria:

- Disable provider or set inactive.
- Remove/deprioritize stale price rows.
- Pause routing to provider.
- Investigate cancellation/finish mismatches without direct wallet edits.

Required docs/runbook updates:

- `docs/SMS_PROVIDER_CONTRACT.md`
- `docs/API_CALLBACKS.md`
- `docs/EXTERNAL_INTEGRATION_READINESS.md`
- provider-specific sandbox runbook

Required tests/checks:

- adapter contract tests
- order/wallet failure-path tests
- polling idempotency tests
- cancellation/finish semantics tests
- price/stock freshness tests
- provider sandbox integration test

### Stage 6: Broader Beta

Entry criteria:

- Friendly buyer beta is stable.
- First supplier sandbox is signed off or supplier features remain disabled for broader buyer traffic.
- Payment provider and SMS provider sandboxes are either signed off or explicitly disabled.
- Incident, support, backup/restore, and monitoring processes have been rehearsed.

Allowed actions:

- Expand buyer cohort gradually.
- Enable signed-off supplier or provider paths behind admin-controlled status/priority.
- Monitor risk, request logs, ops summary, reconciliation, release retries, and wallet ledger.
- Tune rate limits based on observed traffic.

Forbidden actions:

- No public launch.
- No unsupported countries/services/providers.
- No auto-repair of money/reconciliation issues without approved workflow.
- No real payment/SMS provider enablement without signed-off contracts/tests.

Success criteria:

- No unresolved P0 wallet/order/auth bugs.
- Support process handles buyer issues.
- Operators can trace request IDs and reconcile money/order state.
- Abuse/risk monitoring is reviewed regularly.

Rollback criteria:

- Pause invites.
- Disable specific provider/supplier/payment path.
- Revoke compromised sessions/API keys.
- Return to manual_test/mock path if real sandbox path causes issues.

Required docs/runbook updates:

- `docs/EXTERNAL_INTEGRATION_READINESS.md`
- `docs/PRODUCTION_BACKEND_RUNBOOK.md`
- incident/support runbook
- provider/supplier/payment runbooks as used

Required tests/checks:

- RC-style backend tests after code changes
- frontend build/browser smoke after UI changes
- local E2E smoke
- health/ready checks
- backup/restore drill before production launch

## 4. Go / No-Go Gates

| Gate | Current status | Go criteria | No-go conditions |
|---|---|---|---|
| Friendly buyers | Mostly ready, pending RC-2 visual QA | RC-2 browser QA passed; manual_test copy clear; local E2E green; support channel ready | UI/auth flow unverified, wallet/order regression, unclear funding copy |
| First real supplier sandbox | Not ready, close | KYC/contract approval; supplier contract signoff; callback idempotency and release/SMS tests pass | no KYC/contract, no sandbox signoff, reservation/release failures unresolved |
| Real payments | Not ready | Provider-specific checkout, signature verification, amount/currency validation, reconciliation, dispute/refund policy, sandbox pass | generic shared-secret webhook, wrong amount/currency can credit, no provider signature verification |
| Real SMS providers | Not ready | Real adapter, price/stock freshness, credential rotation, cancellation/finish semantics, reconciliation, sandbox pass | placeholder adapter, stale prices, no credential policy, no provider reconciliation |
| Public launch | Not ready | Legal/support/abuse policies, monitoring/alerting, backup/restore drill, load/security verification, signed-off real integrations | any real integration unfinished, no incident process, no monitoring, unresolved P0 ledger/auth/order issues |

## 5. Risk Register

| Risk | Severity | Area | Owner/action suggestion |
|---|---|---|---|
| Browser/mobile visual QA not recorded | P0 before friendly buyers | UI/tests | Run RC-2 browser QA and record exact results. |
| Buyer misunderstanding manual_test funding | P0 before friendly buyers | product/docs/UI | Clarify copy: intent creation does not fund wallet until admin/manual completion or webhook success. |
| Supplier KYC/contract/support process missing | P0 before real supplier | business/legal/ops | Define approval, contract, support, escalation, and sandbox signoff checklist. |
| Supplier application/review and activation browser QA pending | P1 supplier sandbox | UI/tests | Browser-test `/suppliers`, admin supplier application review, `/supplier` activation history, and SMS push correlation before first supplier sandbox. |
| External payout execution not implemented | P1 before production supplier payouts | ops/business/backend | Keep payouts manual/admin; define external settlement process before automation. |
| Real payment signature verification missing | P0 before real payments | backend/security | Implement provider-specific verification per payment contract. |
| Payment amount/currency validation missing | P0 before real payments | backend/accounting | Implement validation before any real wallet crediting. |
| Chargeback/refund/dispute policy missing | P0 before real payments | business/legal/accounting | Define policy and ledger handling before provider launch. |
| Real SMS adapters are placeholders | P0 before real SMS | backend | Implement adapter and sandbox tests per SMS provider contract. |
| Provider price/stock freshness missing | P0 before real SMS | backend/ops | Add sync job, TTL, stale-provider routing behavior, and admin visibility. |
| Provider credential storage/rotation not formalized | P0 before real supplier/provider scale | security/ops | Decide KMS/secret manager and rotation process. |
| Provider reconciliation missing | P1 before real SMS | backend/ops | Add provider reconciliation views/jobs before live routing. |
| External monitoring/alerting absent | P1 before broader beta/public | ops | Add alerting for health, 5xx, 429, wallet/reconciliation anomalies. |
| Backup/restore drill not recorded | P1 before public launch | ops | Run and document restore test. |
| No password reset/MFA | P2 friendly beta, P1 broader beta | backend/security/product | Keep trusted beta small; plan password reset/MFA before broader launch. |
| Risk controls are manual-only | P2 friendly beta, P1 public | ops/product | Review risk dashboard manually; define abuse response before public launch. |

## 6. What Not To Do Yet

- Do not public launch.
- Do not enable real payments before provider-specific signature verification, amount/currency validation, and provider reconciliation are implemented.
- Do not connect real SMS provider traffic before adapter implementation, price/stock freshness, cancellation semantics, and reconciliation are implemented.
- Do not production-onboard suppliers before KYC/contract/support policy and sandbox signoff.
- Do not use legacy fake supplier phone in production/staging.
- Do not direct-edit wallet or supplier balances without ledger transactions.
- Do not expose `provider_cost` or provider credentials.
- Do not let UI polish expand indefinitely before recording browser QA.

## 7. Recommended Next Task

Next task: RC-2 browser visual QA and UI freeze record.

Why:

- Backend readiness has been hardened and documented.
- Real provider/payment work is intentionally gated.
- Friendly buyer closed beta is the next lowest-risk external step, but it still needs a recorded browser/mobile/light/dark QA pass.

Suggested verification:

- `docker compose build frontend`
- `docker run --rm smsbridge-frontend npm run build`
- `python tools/local_e2e_smoke.py`
- browser pass across `/`, `/buy`, `/dashboard`, `/orders`, `/deposit`, `/api-docs`, `/supplier`, `/admin`
- update `docs/UI_READINESS_AUDIT.md` and `docs/EXTERNAL_INTEGRATION_READINESS.md`
