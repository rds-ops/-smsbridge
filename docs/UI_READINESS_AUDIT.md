# UI Readiness Audit

Current external integration readiness is tracked in `docs/EXTERNAL_INTEGRATION_READINESS.md`.
Frontend phase implementation planning is tracked in `docs/FRONTEND_IMPLEMENTATION_ROADMAP.md`.

This is the current UI state audit. Older UI milestone labels such as UI-4/UI-8/UI-14 are intentionally not used as the source of truth here.

## 1. UI Current State

The frontend has moved from a dashboard-first MVP toward a marketplace-first app shell.

Implemented foundations:

- marketplace-first home page at `/`
- `/buy` reuses the marketplace storefront
- top nav with Home, API, Suppliers, FAQ
- account dropdown with Orders, Add funds, Settings, Supplier cabinet, Admin, Logout
- shared auth modal
- dark mode toggle
- local shadcn/ui-compatible primitives
- persistent storefront around buyer/public account pages
- public FAQ page
- public Suppliers page
- API docs page with signed-in managed API key management
- supplier cabinet at `/supplier`

## 2. Buyer/Public UI

Implemented:

- marketplace storefront with service, country, and offer selection
- unauthenticated buy action opens auth modal and preserves selection
- order creation from storefront with `Idempotency-Key`
- inline order status panel after purchase
- cancel/finish actions
- order list and order detail pages
- dashboard wallet summary
- wallet transaction history
- buyer deposit page for `manual_test` payment intent creation/status/history
- API docs page with managed API key create/list/revoke/scopes/usage
- legacy API key regenerate remains available for compatibility
- settings page
- FAQ and Suppliers public pages

Partially implemented:

- storefront has a step flow, but it still needs live browser/mobile polish.
- buyer order detail has status presentation, but it does not expose durable `order_events`; only admin has order event history.
- real payment provider UX is not implemented; `/deposit` is local/manual `manual_test` only.
- account utility pages use the marketplace shell, but some legacy dense page styles still exist.

Missing/deferred:

- real payment provider checkout
- buyer-safe order event timeline endpoint/UI
- public unauthenticated catalog API UX if product requires it
- production-grade mobile QA across storefront/account pages

## 3. Supplier UI

Route:

- `/supplier`

Implemented:

- supplier API-key based access screen
- API key stored in session storage for MVP use
- profile/balance/reward/status from `GET /supplier/v1/me`
- inventory list/update
- SMS push helper
- payout request create/list
- supplier transaction/reward history

Partially implemented:

- supplier activation history backend endpoint now exists, but it is not surfaced in the `/supplier` UI yet.
- supplier API key handling is MVP-style paste-and-store; not a full supplier login/session flow.
- reservation/release health is mostly visible to admins, not suppliers.

Missing/deferred:

- supplier login/JWT or stronger partner auth UX
- supplier activation history UI
- supplier onboarding/KYC/contract flow
- richer payout/accounting explanations

## 4. Admin UI

Route:

- `/admin`

Implemented:

- metrics
- users
- orders
- providers
- suppliers
- supplier reservation config in supplier create/update
- supplier reservation/release visibility fields in supplier inventory
- audit logs
- API request logs with explicit columns and backend-side request-id/method/status filtering
- manual wallet deposit
- ops summary dashboard
- risk users/actions
- payment intent list/detail/manual completion
- supplier payout requests and lifecycle actions
- reliability center:
  - supplier release retries
  - payment reconciliation
  - supplier payout reconciliation
  - cleanup dry-run

Partially implemented:

- supplier inventory/activations/SMS/transactions still require selecting/entering supplier context.
- admin lists are operational but not fully polished for high volume.
- dark mode styling is functional but needs a pass on dense admin tables.

Missing/deferred:

- real provider sync/credential UI
- external payout execution UI
- richer logs/metrics dashboards
- bulk moderation/support workflows

## 5. Current UI Readiness by Area

| Area | Status | Notes |
|---|---|---|
| Local demo buyer flow | Mostly ready | RC-1 frontend build, route availability, and local E2E smoke passed; true visual browser/mobile QA remains. |
| Buyer wallet/manual deposit flow | Mostly ready | `manual_test` creation exists; admin completion remains admin-only. |
| Managed API keys | Mostly ready | Create/list/revoke/scopes/usage implemented. |
| Supplier cabinet MVP | Mostly ready | Profile/inventory/SMS/payouts/transactions implemented; activation history backend exists but UI is missing. |
| Admin operations | Mostly ready | Ops/risk/payments/payouts/reliability/logs implemented. |
| Real payment UX | Not ready | Real providers deferred. |
| Real supplier onboarding UX | Not ready | No onboarding/KYC/session flow. |
| Real provider operations UI | Not ready | Real adapters/sync not implemented. |

## 6. Remaining UI Gaps

Beta blockers or near-blockers:

- complete true visual browser/mobile QA after latest layout/auth changes
- clarify `/deposit` copy so buyers understand admin/manual completion
- verify auth false redirects and token refresh behavior in browser
- mobile storefront QA

Beta useful:

- buyer-safe order event timeline after backend endpoint exists
- supplier activation history UI
- improved admin pagination/filtering on high-volume tables
- better supplier payout/accounting explanations
- docs links from UI to local E2E/manual_test flows

Later:

- real payment provider checkout UX
- real supplier onboarding/KYC UI
- provider credential/sync UI
- external observability dashboard integration

## 7. Top Remaining UI Tasks

Screen-by-screen implementation order is tracked in `docs/FRONTEND_IMPLEMENTATION_ROADMAP.md`. This section remains a short audit summary.

| Task | Area | Priority | Complexity | Why |
|---|---|---|---|---|
| Browser smoke pass for storefront auth/order/deposit | frontend/tests | blocker | medium | Confirms recent shell/auth changes work together. |
| Mobile storefront QA/fixes | frontend | beta-useful | medium | Marketplace-first home must work on phones. |
| Clarify manual_test funding copy | frontend/docs | blocker | small | Avoids misleading friendly buyers. |
| Buyer order event timeline | backend/frontend | later | medium | Requires buyer-safe event endpoint first. |
| Supplier activation history UI | frontend | beta-useful | medium | Backend endpoint exists; real suppliers need visibility in the cabinet. |
| Admin high-volume pagination polish | frontend/backend | beta-useful | medium | Keeps ops pages usable as data grows. |
| Supplier onboarding UX | product/frontend | later | large | Needed before real supplier acquisition. |
| Real payment provider UX | frontend/backend | later | large | Deferred until provider implementation. |
| Provider operations UI | frontend/backend | later | large | Depends on real provider adapter/sync work. |
| Dark mode polish for dense admin/supplier pages | frontend | later | small | Visual polish, not core readiness. |

## 8. RC-1 UI Verification Record

Date: 2026-06-27

Passed:

- `docker compose build frontend`
- `docker run --rm smsbridge-frontend npm run build`
- `docker compose up -d frontend`
- HTTP route availability checks for `/`, `/buy`, `/dashboard`, `/orders`, `/deposit`, `/api-docs`, `/supplier`, and `/admin`; all returned HTTP 200.
- `python tools/local_e2e_smoke.py` passed the local manual/mock E2E flow, including manual_test payment completion, supplier reservation, supplier SMS, order finish, wallet ledger, and supplier reward.

Not completed:

- True visual browser QA for desktop/mobile and light/dark mode. The in-app browser connector failed during setup, so RC-1 records route availability but not a visual pass.
