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
- frontend logout calls backend logout when a refresh token exists, and settings includes a current-user logout-all control
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
- supplier activation history list with safe summary fields
- SMS push helper
- payout request create/list
- supplier transaction/reward history

Partially implemented:

- supplier activation history is surfaced, but still needs focused browser QA with SMS push correlation before supplier sandbox.
- supplier API key handling is MVP-style paste-and-store; not a full supplier login/session flow.
- reservation/release health is mostly visible to admins, not suppliers.

Missing/deferred:

- supplier login/JWT or stronger partner auth UX
- supplier activation history browser QA with SMS push correlation
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
- user session revoke-all action from the Users table
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
| Local demo buyer flow | Ready | RC-1 frontend build/local E2E passed; RC-2 browser QA passed after small responsive fixes. |
| Buyer wallet/manual deposit flow | Ready for manual/mock beta | `manual_test` creation exists; admin completion remains admin-only and copy is visible. |
| Managed API keys | Mostly ready | Create/list/revoke/scopes/usage implemented. |
| Supplier cabinet MVP | Mostly ready | Profile/inventory/activations/SMS/payouts/transactions implemented and RC-2 route checks passed; activation history still needs focused browser QA. |
| Admin operations | Mostly ready | Ops/risk/payments/payouts/reliability/logs implemented; RC-2 admin route check passed. |
| Real payment UX | Not ready | Real providers deferred. |
| Real supplier onboarding UX | Not ready | No onboarding/KYC/session flow. |
| Real provider operations UI | Not ready | Real adapters/sync not implemented. |

## 6. Remaining UI Gaps

Beta blockers or near-blockers:

- no active RC-2 buyer UI blocker after the recorded browser pass
- verify token refresh/logout/logout-all behavior during longer manual sessions

Beta useful:

- buyer-safe order event timeline after backend endpoint exists
- supplier activation history browser QA with SMS push correlation
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
| Longer authenticated session/logout browser pass | frontend/tests | beta-useful | small | Backend logout/logout-all is wired; longer-session browser behavior still needs a focused pass. |
| Supplier activation history browser QA | frontend/tests | beta-useful | small | UI is wired; real suppliers need a verified activation/SMS workflow in the cabinet. |
| Admin user session revoke-all browser QA | frontend/tests | beta-useful | small | UI action is wired; confirm operator workflow in browser. |
| Buyer order event timeline | backend/frontend | later | medium | Requires buyer-safe event endpoint first. |
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

## 9. RC-2 Browser QA Record

Date: 2026-06-29

Browser/tool used:

- Local Docker Compose services: frontend/backend/postgres/redis.
- Headless Chrome `149.0.7827.199` driven through Chrome DevTools Protocol.
- The in-app browser connector failed before opening a page, so local headless Chrome was used as the browser QA fallback.

Routes checked:

- `/`
- `/buy`
- `/dashboard`
- `/orders`
- `/deposit`
- `/api-docs`
- `/supplier`
- `/admin`

Themes checked:

- light
- dark

Viewports checked:

- desktop 1440px
- laptop 1024px
- mobile 390px

Initial issues found:

- Guest nav actions overflowed mobile width by roughly 27px on public/storefront/supplier pages.
- `/api-docs` code/example cards overflowed mobile and laptop widths because long code blocks forced grid/card min-width expansion.
- Repeated scripted admin logins temporarily hit the Redis rate limiter; this was a QA-script side effect, not a UI failure.

Fixes applied:

- Reduced guest nav button minimum width on small screens and tightened the nav action gap.
- Added `min-w-0` to the shared `Card` wrapper so long tables/code blocks can shrink inside responsive grids.

Verification after fixes:

- `docker-compose build frontend`: PASS
- `docker run --rm smsbridge-frontend npm run build`: PASS
- `docker-compose up -d frontend`: PASS
- Focused post-fix browser checks for `/`, `/buy`, `/api-docs`, and `/supplier` passed on mobile 390px and laptop 1024px in both light and dark themes with no horizontal overflow.
- Authenticated desktop checks passed for `/dashboard`, `/orders`, `/deposit`, `/api-docs`, and `/admin`.
- Login modal opens from the public nav.

RC-2 status:

- UI Freeze Candidate for mock/manual closed beta.

Remaining non-blocking gaps:

- Frontend logout/logout-all is wired to backend endpoints; longer-session browser QA remains useful.
- Supplier activation history UI is wired; focused Phase C browser QA remains for supplier sandbox.
- Admin target-user session revoke-all UI is wired; browser QA remains useful for operator workflow.
- Real payment provider UX and real SMS provider operations UI remain deferred until backend integration gates open.
