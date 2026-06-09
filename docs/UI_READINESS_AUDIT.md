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

Task 49 update: the admin ops summary dashboard is now implemented in the existing admin UI.

## 1. Current Frontend Coverage

### Buyer UI

Implemented:
- Login/register/session handling.
- Dashboard with balance, held balance, limits, active/completed order counts, recent orders.
- Buy flow using services, countries, prices, balance, and `POST /api/v1/orders`.
- Order list with filters and cancel/finish actions.
- Order detail with phone number, SMS code/text, balance refresh, cancel/finish actions.
- Legacy API key regeneration on `/api-docs` through `POST /api/v1/api-key/regenerate`.
- Static API examples for balance/prices/orders.

Partially implemented:
- API key UX exists only for legacy single-key regeneration. Managed API keys/scopes/usage are not represented.
- Order detail has a static four-step timeline, but it does not use durable `order_events`.
- Payment/deposit UX still depends on admin manual deposit, not buyer payment intents/manual completion flow.

### Supplier UI

Implemented:
- No supplier-facing cabinet/login UI exists.

Admin-only supplier views implemented:
- Supplier create/update/status/reward/API key generation.
- Supplier inventory list by supplier ID.
- Supplier activations list by supplier ID.
- Supplier SMS list by supplier ID.
- Supplier transactions list by supplier ID.

Partially implemented:
- Supplier reservation config fields and reservation visibility exist in backend, but frontend supplier create/update/types do not expose them.
- Supplier inventory visibility fields are not typed/rendered.

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

Partially implemented:
- API request logs are rendered generically but the explicit table columns omit newer fields such as `request_id`, `supplier_id`, and `buyer_api_key_id`.
- Supplier inventory/activations/SMS/transactions are visible only via manually entering supplier ID.

Missing:
- Payment intent admin list/detail/manual-complete.
- Payment credit reconciliation.
- Supplier payout requests/admin actions/reconciliation.
- Supplier release retry queue.
- Operational cleanup dry-run.
- Admin request log filtering/search by request ID.

## 2. Missing UI Plan

### Buyer UI

| Item | Backend endpoint(s) | Likely frontend files | Priority | Complexity |
| --- | --- | --- | --- | --- |
| Wallet transaction history | `GET /api/v1/wallet/transactions` | `apps/frontend/lib/client/api.ts`, `apps/frontend/lib/shared/types.ts`, `apps/frontend/app/dashboard/page.tsx` or new `apps/frontend/app/wallet/page.tsx`, nav/translations | beta blocker | small |
| Payment intents and local `manual_test` deposit flow | `POST /api/v1/payment-intents`, `GET /api/v1/payment-intents/{public_id}`, admin completion remains admin-only | client API/types, new buyer deposit page, admin payment intent page for manual completion, docs/API page | beta useful | medium |
| Managed API keys list/create/revoke | `POST /api/v1/api-keys`, `GET /api/v1/api-keys`, `POST /api/v1/api-keys/{public_id}/revoke` | `apps/frontend/lib/client/api.ts`, shared types, `apps/frontend/app/settings/page.tsx` or new `apps/frontend/app/api-keys/page.tsx`, `apps/frontend/app/api-docs/page.tsx` | beta useful | medium |
| API key usage visibility | `GET /api/v1/api-keys/{public_id}/usage` | same API key page/types | later | small |
| API key scopes UX | managed API key create/list endpoints | API key page, scope selector constants/translations | beta useful | medium |
| Payment intent status visibility | `GET /api/v1/payment-intents/{public_id}` | buyer deposit/payment intent detail/list page | later | small |
| Order events/status details | No buyer endpoint currently; admin endpoint exists at `GET /admin/orders/{order_id}/events` only | no buyer UI until backend buyer-safe endpoint exists | later | medium |
| Idempotency-Key support in buy flow | `POST /api/v1/orders` with `Idempotency-Key` header | `apps/frontend/lib/client/api.ts`, `apps/frontend/app/buy/page.tsx` | beta useful | small |

### Supplier UI

| Item | Backend endpoint(s) | Likely frontend files | Priority | Complexity |
| --- | --- | --- | --- | --- |
| Supplier login/API key session | `GET /supplier/v1/me`, supplier bearer API key auth | new supplier auth/session helper, new `apps/frontend/app/supplier/*`, nav separation | beta useful | large |
| Supplier profile and balances | `GET /supplier/v1/me` | supplier dashboard page/types | beta useful | medium |
| Supplier inventory list/update | `GET /supplier/v1/inventory`, `POST /supplier/v1/inventory/update` | supplier dashboard/inventory page | beta useful | medium |
| Supplier payout request create/list | `POST /supplier/v1/payout-requests`, `GET /supplier/v1/payout-requests` | supplier payout page/types | beta useful | medium |
| Supplier SMS push helper | `POST /supplier/v1/sms` | supplier dev/testing page or local integration helper UI | later | medium |
| Supplier activations view | No supplier-facing activation list endpoint currently; admin-only exists | requires backend endpoint before supplier UI | later | medium |
| Supplier reward transaction history | No supplier-facing transaction endpoint currently; admin-only exists | requires backend endpoint before supplier UI | beta useful | medium |
| Reservation/release callback docs/status | docs plus admin config endpoints only | supplier docs page/static guidance | later | small |

### Admin UI

| Item | Backend endpoint(s) | Likely frontend files | Priority | Complexity |
| --- | --- | --- | --- | --- |
| Payment intent admin visibility | `GET /admin/payment-intents`, `GET /admin/payment-intents/{id}` | admin API/types/page tabs | beta blocker | medium |
| Admin manual payment completion | `POST /admin/payment-intents/{id}/manual-complete` | admin payment intent table action | beta blocker | small |
| Payment credit reconciliation | `GET /admin/payment-intents/reconciliation` | admin reconciliation tab/cards | beta useful | small |
| Supplier payout request admin flow | `GET /admin/supplier-payout-requests`, `GET /admin/supplier-payout-requests/{id}`, approve/reject/mark-paid endpoints | admin API/types/page tabs/actions | beta blocker | medium |
| Supplier payout reconciliation | `GET /admin/supplier-payout-requests/reconciliation` | admin reconciliation tab/cards | beta useful | small |
| Supplier release retries | `GET /admin/supplier-release-retries` | admin API/types/page tab | beta blocker | small |
| Operational cleanup dry-run | `POST /admin/ops/cleanup/dry-run` | admin ops tab/action | beta useful | small |
| Request logs with request ID | `GET /admin/api-request-logs` includes `request_id`, `supplier_id`, `buyer_api_key_id` | shared types/admin table columns/filter input | beta useful | small |
| Supplier reservation config | `POST/PATCH /admin/suppliers`, `GET /admin/suppliers` fields | admin supplier form/types/table | beta blocker | medium |
| Supplier reservation visibility fields | `GET /admin/suppliers/{id}/inventory` fields | supplier inventory type/table columns | beta useful | small |

## 3. Top 10 UI Tasks

1. Admin payment intent list/detail/manual-complete.
   - Endpoints: `/admin/payment-intents*`
   - Priority: beta blocker
   - Complexity: medium

2. Admin supplier payout request list/detail/actions.
   - Endpoints: `/admin/supplier-payout-requests*`
   - Priority: beta blocker
   - Complexity: medium

3. Admin supplier release retry queue.
   - Endpoint: `GET /admin/supplier-release-retries`
   - Priority: beta blocker
   - Complexity: small

4. Admin supplier reservation config in supplier create/update.
   - Endpoints: `POST /admin/suppliers`, `PATCH /admin/suppliers/{supplier_id}`
   - Priority: beta blocker
   - Complexity: medium

5. Buyer wallet transaction history.
   - Endpoint: `GET /api/v1/wallet/transactions`
   - Priority: beta blocker
   - Complexity: small

6. Managed buyer API keys with scopes.
   - Endpoints: `/api/v1/api-keys*`
   - Priority: beta useful
   - Complexity: medium

7. Request log request ID visibility and filtering.
   - Endpoint: `GET /admin/api-request-logs`
   - Priority: beta useful
   - Complexity: small

8. Payment/payout reconciliation cards.
   - Endpoints: `GET /admin/payment-intents/reconciliation`, `GET /admin/supplier-payout-requests/reconciliation`
   - Priority: beta useful
   - Complexity: small

9. Operational cleanup dry-run.
    - Endpoint: `POST /admin/ops/cleanup/dry-run`
    - Priority: beta useful
    - Complexity: small

10. API key usage visibility.
    - Endpoint: `GET /api/v1/api-keys/{public_id}/usage`
    - Priority: later
    - Complexity: small

## 4. Beta Readiness

Frontend is not closed-beta ready for operations-heavy use.

It is usable for the basic buyer flow and basic admin setup:
- buyer login/register
- balance view
- buy/cancel/finish orders
- basic admin metrics/users/orders/providers/suppliers
- manual admin wallet deposit

It is not ready for closed beta operations because major implemented backend controls are missing from UI:
- no payment intent/manual completion UI
- no payout operations UI
- no release retry queue UI
- no buyer wallet ledger UI
- no managed API key UI
- no supplier cabinet

## 5. Biggest Gaps

1. Admin operations are still the largest gap. The admin UI now has ops summary, but risk actions, reconciliation, retries, request ID filtering, and cleanup dry-run are still missing.

2. Buyer accounting transparency is incomplete. The backend exposes wallet transaction history and payment intents, but the frontend still shows only balances and manual admin-deposit assumptions.

3. API key management is outdated in UI. The frontend still centers the legacy regenerate endpoint, while the backend supports managed keys, scopes, revocation, and usage visibility.

4. Supplier UX is mostly absent. Supplier APIs exist for profile, inventory, SMS, and payout requests, but there is no supplier-facing frontend session or cabinet.

5. Local E2E flow is documented but not surfaced in UI. The app has a developer commands page and API docs page, but they do not reflect the current manual_test payment intent + fake supplier reservation flow.
