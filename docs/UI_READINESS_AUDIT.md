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
Task 56 update: admin API request logs now show explicit operational columns and frontend-side `request_id` filtering.
Task 57 update: buyer manual_test deposit/payment intent creation and status visibility are now implemented at `/deposit`.

## 1. Current Frontend Coverage

### Buyer UI

Implemented:
- Login/register/session handling.
- Dashboard with balance, held balance, limits, active/completed order counts, recent orders.
- Buy flow using services, countries, prices, balance, and `POST /api/v1/orders`.
- Order list with filters and cancel/finish actions.
- Order detail with phone number, SMS code/text, balance refresh, cancel/finish actions.
- Wallet transaction history on the dashboard from `GET /api/v1/wallet/transactions`.
- Buyer manual_test deposit/payment intent creation and status visibility at `/deposit`.
- Managed API key list/create/revoke/scopes/usage on `/api-docs`.
- Legacy API key regeneration on `/api-docs` through `POST /api/v1/api-key/regenerate`.
- Static API examples for balance/prices/orders.

Partially implemented:
- Order detail has a static four-step timeline, but it does not use durable `order_events`.
- Payment/deposit UX supports local `manual_test` payment intent creation, but real payment provider UX is still deferred and completion remains admin-only.

### Supplier UI

Implemented:
- Supplier API-key session screen at `/supplier`.
- Supplier profile, balances, reward percent and status from `GET /supplier/v1/me`.
- Supplier inventory list/update from `GET /supplier/v1/inventory` and `POST /supplier/v1/inventory/update`.
- Supplier payout request create/list from `POST /supplier/v1/payout-requests` and `GET /supplier/v1/payout-requests`.

Admin-only supplier views implemented:
- Supplier create/update/status/reward/API key generation.
- Supplier inventory list by supplier ID.
- Supplier activations list by supplier ID.
- Supplier SMS list by supplier ID.
- Supplier transactions list by supplier ID.

Partially implemented:
- Supplier reservation config fields and reservation visibility exist in backend, but frontend supplier create/update/types do not expose them.
- Supplier SMS push helper is not implemented in the supplier cabinet yet.
- Supplier activation/reward history remains admin-only because no supplier-facing endpoints exist yet.

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
- API request logs show `request_id`, identity columns and frontend-side request ID filtering, but there is no backend request ID query/filter endpoint yet.
- Supplier inventory/activations/SMS/transactions are visible only via manually entering supplier ID.

Missing:
- Backend-side admin request log filtering/search by request ID.

## 2. Missing UI Plan

### Buyer UI

| Item | Backend endpoint(s) | Likely frontend files | Priority | Complexity |
| --- | --- | --- | --- | --- |
| Real payment provider deposit UX | Future provider-backed payment intent flow | buyer deposit page/provider selection | later | large |
| Order events/status details | No buyer endpoint currently; admin endpoint exists at `GET /admin/orders/{order_id}/events` only | no buyer UI until backend buyer-safe endpoint exists | later | medium |
| Idempotency-Key support in buy flow | `POST /api/v1/orders` with `Idempotency-Key` header | `apps/frontend/lib/client/api.ts`, `apps/frontend/app/buy/page.tsx` | beta useful | small |

### Supplier UI

| Item | Backend endpoint(s) | Likely frontend files | Priority | Complexity |
| --- | --- | --- | --- | --- |
| Supplier SMS push helper | `POST /supplier/v1/sms` | supplier dev/testing page or local integration helper UI | later | medium |
| Supplier activations view | No supplier-facing activation list endpoint currently; admin-only exists | requires backend endpoint before supplier UI | later | medium |
| Supplier reward transaction history | No supplier-facing transaction endpoint currently; admin-only exists | requires backend endpoint before supplier UI | beta useful | medium |
| Reservation/release callback docs/status | docs plus admin config endpoints only | supplier docs page/static guidance | later | small |

### Admin UI

| Item | Backend endpoint(s) | Likely frontend files | Priority | Complexity |
| --- | --- | --- | --- | --- |
| Supplier reservation config | `POST/PATCH /admin/suppliers`, `GET /admin/suppliers` fields | admin supplier form/types/table | beta blocker | medium |
| Supplier reservation visibility fields | `GET /admin/suppliers/{id}/inventory` fields | supplier inventory type/table columns | beta useful | small |

## 3. Top 10 UI Tasks

1. Admin supplier reservation config in supplier create/update.
   - Endpoints: `POST /admin/suppliers`, `PATCH /admin/suppliers/{supplier_id}`
   - Priority: beta blocker
   - Complexity: medium

2. Supplier reservation visibility fields.
    - Endpoint: `GET /admin/suppliers/{id}/inventory`
    - Priority: beta useful
    - Complexity: small

3. Backend-side request log request ID filtering.
   - Endpoint: `GET /admin/api-request-logs`
   - Priority: later
   - Complexity: small

4. Supplier SMS push helper.
    - Endpoint: `POST /supplier/v1/sms`
    - Priority: later
    - Complexity: medium

5. Supplier reward transaction history.
    - Endpoint: not implemented supplier-side yet
    - Priority: beta useful
    - Complexity: medium

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

It is closer to closed-beta readiness after the operations/admin and supplier cabinet work, but still has gaps in admin supplier reservation configuration, request-log filtering, and buyer payment intent UX.

## 5. Biggest Gaps

1. Admin operations are still the largest gap. The admin UI now has ops summary, risk actions, payment intent manual completion, supplier payout operations, retries, reconciliation, and cleanup dry-run visibility, but request ID filtering and supplier reservation configuration are still missing.

2. Buyer accounting transparency is improved with wallet transaction history and manual_test payment intent creation/status visibility. Real payment provider UX is still deferred, and manual completion remains admin-only.

3. API key management now supports managed keys, scopes, revocation and usage, while the legacy regenerate endpoint remains for compatibility.

4. Supplier UX now has an API-key cabinet for profile, inventory and payout requests. Supplier SMS helper, activation history and reward transaction history remain later.

5. Local E2E flow is documented but not surfaced in UI. The app has a developer commands page and API docs page, but they do not reflect the current manual_test payment intent + fake supplier reservation flow.
