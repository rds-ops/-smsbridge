# UI Readiness Audit

Draft/internal audit of frontend coverage for the currently implemented backend APIs.

Scope inspected:
- `apps/frontend/app/*`
- `apps/frontend/components/*`
- `apps/frontend/lib/client/api.ts`
- `apps/frontend/lib/admin/api.ts`
- `apps/frontend/lib/shared/api.ts`
- `apps/frontend/lib/shared/types.ts`
- `docs/API_BUYER.md`
- `docs/API_SUPPLIER.md`
- `docs/API_CALLBACKS.md`
- `docs/API_AUDIT.md`

Task 55 update: the supplier API-key cabinet MVP is now implemented at `/supplier`.
Task 56 update: admin API request logs now show explicit operational columns.
Task 64 update: admin API request logs now support backend-side filters for request ID, identity fields, method, endpoint, status, limit and offset.
Task 57 update: buyer manual_test deposit/payment intent creation and status visibility are now implemented at `/deposit`.
Task 65 update: supplier-scoped transaction/reward history is now implemented at `/supplier`.
Task UI-3 update: `/` is now marketplace-first, `/buy` reuses the same marketplace, the old buyer sidebar shell was removed, and unauthenticated buy opens an auth gate while preserving selection.
Task UI-4 update: local shadcn/ui foundation components were added, the top navigation spacing was cleaned up, and buyer account routes now render inside the marketplace shell with the storefront visible.

## 1. Current Frontend Coverage

### Buyer UI

Implemented:
- Login/register/session handling.
- Dashboard with balance, held balance, limits, active/completed order counts, recent orders.
- Public `/` marketplace storefront with service/country/operator selection before login.
- Buy flow using services, countries, prices, balance, and `POST /api/v1/orders`.
- `/buy` reuses the same marketplace experience as `/` for backward compatibility.
- `/orders`, `/orders/{public_id}`, `/deposit`, `/api-docs`, and `/settings` render beside the persistent marketplace storefront.
- Buy flow sends an `Idempotency-Key` on order creation to reduce duplicate order risk on retries/double-clicks.
- Unauthenticated marketplace buy opens an auth gate on the same page, preserves selected service/country/operator, and requires explicit post-login purchase confirmation.
- Successful marketplace purchase shows inline order status with phone, SMS code/text, cancel/finish actions and full order-detail fallback link.
- Order list with filters and cancel/finish actions.
- Order detail with phone number, SMS code/text, balance refresh, cancel/finish actions.
- Wallet transaction history on the dashboard from `GET /api/v1/wallet/transactions`.
- Buyer manual_test deposit/payment intent creation and status visibility at `/deposit`.
- Buyer payment intent history/list on `/deposit` from `GET /api/v1/payment-intents`.
- Managed API key list/create/revoke/scopes/usage on `/api-docs`.
- Legacy API key regeneration on `/api-docs` through `POST /api/v1/api-key/regenerate`.
- Static API examples for balance/prices/orders.

Partially implemented:
- Order detail has a static four-step timeline, but it does not use durable `order_events`.
- Payment/deposit UX supports local `manual_test` payment intent creation, but real payment provider UX is still deferred and completion remains admin-only.
- Account utility pages now use top navigation instead of the old dashboard-style buyer sidebar.
- shadcn/ui-compatible base components exist locally for button, card, input, dialog, badge, tabs, dropdown menu, sheet, separator and table. Further migration is incremental.

### Supplier UI

Implemented:
- Supplier API-key session screen at `/supplier`.
- Supplier profile, balances, reward percent and status from `GET /supplier/v1/me`.
- Supplier inventory list/update from `GET /supplier/v1/inventory` and `POST /supplier/v1/inventory/update`.
- Supplier SMS push helper from `POST /supplier/v1/sms`.
- Supplier payout request create/list from `POST /supplier/v1/payout-requests` and `GET /supplier/v1/payout-requests`.
- Supplier transaction/reward history from `GET /supplier/v1/transactions`.

Admin-only supplier views implemented:
- Supplier create/update/status/reward/API key generation.
- Supplier inventory list by supplier ID.
- Supplier activations list by supplier ID.
- Supplier SMS list by supplier ID.
- Supplier transactions list by supplier ID.

Partially implemented:
- Supplier activation history remains admin-only because no supplier-facing activation list endpoint exists yet.

### Admin UI

Implemented:
- Metrics page from `GET /admin/metrics`.
- Users table from `GET /admin/users`.
- Orders table from `GET /admin/orders`.
- Providers table from `GET /admin/providers`.
- Suppliers table and supplier detail tables.
- Audit logs table.
- API request logs table.
- Manual wallet deposit.
- Ops summary dashboard from `GET /admin/ops/summary`.
- Risk users/actions from `/admin/risk/users*`.
- Payment intent admin list/detail/manual-complete from `/admin/payment-intents*`.
- Supplier payout requests/admin actions from `/admin/supplier-payout-requests*`.
- Reliability Center with supplier release retries, payment reconciliation, supplier payout reconciliation, and cleanup dry-run visibility.

Partially implemented:
- Supplier inventory/activations/SMS/transactions are visible only via manually entering supplier ID.

## 2. Missing UI Plan

### Buyer UI

| Item | Backend endpoint(s) | Likely frontend files | Priority | Complexity |
| --- | --- | --- | --- | --- |
| Real payment provider deposit UX | Future provider-backed payment intent flow | buyer deposit page/provider selection | later | large |
| Order events/status details | No buyer endpoint currently; admin endpoint exists at `GET /admin/orders/{order_id}/events` only | no buyer UI until backend buyer-safe endpoint exists | later | medium |
| Idempotency-Key support in buy flow | `POST /api/v1/orders` with `Idempotency-Key` header | implemented in buyer API client and `/buy` submit flow | implemented | small |

### Supplier UI

| Item | Backend endpoint(s) | Likely frontend files | Priority | Complexity |
| --- | --- | --- | --- | --- |
| Supplier activations view | No supplier-facing activation list endpoint currently; admin-only exists | requires backend endpoint before supplier UI | later | medium |
| Supplier reward transaction history | `GET /supplier/v1/transactions` | implemented in `/supplier` transactions tab | implemented | medium |
| Reservation/release callback docs/status | docs plus admin config endpoints only | supplier docs page/static guidance | later | small |

### Admin UI

| Item | Backend endpoint(s) | Likely frontend files | Priority | Complexity |
| --- | --- | --- | --- | --- |
| Supplier reservation config | `POST/PATCH /admin/suppliers`, `GET /admin/suppliers` fields | implemented in admin supplier create/update UI | implemented | medium |
| Supplier reservation visibility fields | `GET /admin/suppliers/{id}/inventory` fields | implemented in admin supplier inventory table | implemented | small |

## 3. Top 10 UI Tasks

1. Admin supplier reservation config in supplier create/update.
   - Status: implemented.
   - Endpoints: `POST /admin/suppliers`, `PATCH /admin/suppliers/{supplier_id}`
   - Notes: UI exposes reservation enabled, URL, auth type, write-only auth secret and timeout. Stored secrets are not shown.

2. Supplier reservation visibility fields.
    - Status: implemented.
    - Endpoint: `GET /admin/suppliers/{id}/inventory`
    - Notes: UI exposes last reservation/release timestamps, last errors and failed attempt counts.

3. Backend-side request log request ID filtering.
   - Status: implemented.
   - Endpoint: `GET /admin/api-request-logs`
   - Notes: Admin UI sends backend filters for request ID, method and status. Backend also supports user, supplier, buyer API key, endpoint, limit and offset filters.

4. Supplier reward transaction history.
    - Status: implemented.
    - Endpoint: `GET /supplier/v1/transactions`
    - Notes: supplier-scoped, safe fields only, with load-more pagination in `/supplier`.

6. Real payment provider deposit UX.
    - Endpoint: future provider-specific payment integration
    - Priority: later
    - Complexity: large

## 4. Beta Readiness

Frontend is not closed-beta ready for operations-heavy use.

It is usable for the basic buyer flow and basic admin setup:
- buyer login/register
- balance view
- buy/cancel/finish orders
- basic admin metrics/users/orders/providers/suppliers
- manual admin wallet deposit

It is closer to closed-beta readiness after the operations/admin and supplier cabinet work. Remaining gaps are now more focused on supplier-facing reward history, buyer-safe order event visibility, and deferred real payment/provider work.

## 5. Biggest Gaps

1. Admin operations are much stronger after ops summary, risk actions, payment intent manual completion, supplier payout operations, retries, reconciliation, cleanup dry-run visibility, supplier reservation configuration, and backend request-log filtering. Remaining admin gaps are mostly pagination/filter polish and broader operational reporting.

2. Buyer accounting transparency is improved with wallet transaction history, manual_test payment intent creation/status visibility, and buyer payment intent history on `/deposit`. Real payment provider UX is still deferred, and manual completion remains admin-only.

3. API key management now supports managed keys, scopes, revocation and usage, while the legacy regenerate endpoint remains for compatibility.

4. Supplier UX now has an API-key cabinet for profile, inventory, SMS push testing, payout requests and transaction/reward history. Supplier activation history remains later because a supplier-facing endpoint does not exist yet.

5. Local E2E flow is documented but not surfaced in UI. The app has a developer commands page and API docs page, but they do not reflect the current manual_test payment intent + fake supplier reservation flow.
