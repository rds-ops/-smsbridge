# Frontend Implementation Roadmap

Draft/internal. This roadmap maps already implemented backend capabilities to frontend implementation work after backend internal phase completion. It is not a feature wishlist and does not introduce new backend/API scope.

Source of truth inputs:

- `docs/API_AUDIT.md`
- `docs/UI_READINESS_AUDIT.md`
- `docs/EXTERNAL_INTEGRATION_READINESS.md`
- `docs/EXTERNAL_ONBOARDING_ROADMAP.md`
- `docs/ARCHITECTURE_MAP.md`
- `apps/frontend`
- `apps/backend/app/api`

## 1. Current Frontend Status

Estimated frontend completion for mock/manual closed beta: **85%**.

Meaning:

- Buyer local/demo flows are mostly implemented.
- Admin operational surfaces are mostly implemented.
- Supplier cabinet MVP is mostly implemented.
- RC-2 browser/mobile/light/dark QA is recorded and passed after small responsive fixes.
- Several backend-complete capabilities are not fully wired in UI yet.
- Real payment, real SMS provider, and real supplier onboarding UX remain out of scope until corresponding backend/business gates are opened.

## 2. Buyer Screens

| Screen | Current status | Backend API | Backend readiness | Frontend readiness | Remaining UI work | Blocking? | Can postpone until beta? |
|---|---|---|---|---|---|---:|---:|
| Landing `/` | Implemented | Catalog/prices through `/api/v1/services`, `/countries`, `/prices` when authenticated | Complete for mock/manual beta | Mostly ready | Browser QA for desktop/mobile/light/dark | Yes for RC-2 | No |
| Marketplace `/buy` | Implemented | `GET /api/v1/services`, `/countries`, `/prices`; `POST /api/v1/orders` | Complete | Mostly ready | Browser QA for service-first/country-first/operator/review/guest auth | Yes for RC-2 | No |
| Buy flow | Implemented | `POST /api/v1/orders` with `Idempotency-Key`; cancel/finish endpoints | Complete | Mostly ready | Verify idempotency key handling and auth modal behavior in browser | Yes for RC-2 | No |
| Dashboard `/dashboard` | Implemented | `GET /api/v1/balance`, `/limits`, `/orders`, `/wallet/transactions` | Complete | Mostly ready | Browser QA and empty/error states check | Yes for RC-2 | No |
| Orders `/orders`, `/orders/{public_id}` | Implemented | `GET /api/v1/orders`, `GET /orders/{public_id}`, cancel, finish | Complete | Mostly ready | Browser QA for active polling/cancel/finish; buyer order events are backend-admin only, so timeline is deferred | Yes for RC-2 | No |
| Wallet history | Implemented in dashboard | `GET /api/v1/wallet/transactions` | Complete | Mostly ready | Verify pagination/load-more behavior in browser | Beta useful | Yes |
| Deposit `/deposit` | Implemented for `manual_test` | `POST /api/v1/payment-intents`, `GET /api/v1/payment-intents`, detail | Complete for manual/local only | Mostly ready | Confirm copy says admin/manual completion is required; browser QA | Yes for friendly-buyer clarity | No |
| Settings `/settings` | Implemented basic account/settings | `GET /auth/me`; frontend local logout only | Backend logout exists | Partial | Wire logout to `POST /auth/logout`; optionally expose current-user `POST /auth/logout-all` if kept simple | Beta useful | Yes for small friendly beta |
| API docs `/api-docs` | Implemented public docs + signed-in key management | `POST/GET /api/v1/api-keys`, revoke, usage; legacy regenerate | Complete | Mostly ready | Browser QA for create raw-key-once, scopes, usage, revoke | Yes for API beta | No if only browser buyers |
| Auth modal/pages | Implemented | `/auth/login`, `/auth/register`, `/auth/refresh`, `/auth/logout`, `/auth/logout-all` | Complete | Partial | Login/register modal QA; protected-route behavior; backend logout/logout-all wiring | Yes for RC-2 modal QA | Logout-all can wait |

## 3. Supplier Screens

| Screen | Current status | Backend API | Backend readiness | Frontend readiness | Remaining UI work | Blocking? | Can postpone until beta? |
|---|---|---|---|---|---|---:|---:|
| Supplier cabinet `/supplier` | Implemented MVP | Supplier API-key auth across `/supplier/v1/*` | Complete for sandbox API | Mostly ready | Browser QA for pasted key, session storage, refresh, errors | Beta useful | Yes for buyer-only beta |
| Dashboard/profile | Implemented | `GET /supplier/v1/me` | Complete | Mostly ready | Browser QA | No for buyer beta | Yes |
| Inventory | Implemented | `GET /supplier/v1/inventory`, `POST /inventory/update` | Complete | Mostly ready | Browser QA for update form and validation | No for buyer beta | Yes |
| Activation history | Missing in supplier UI | `GET /supplier/v1/activations` | Complete | Missing | Add typed supplier client method, type, tab/table, filters if simple | Blocker for supplier sandbox visibility | Yes for buyer beta |
| Transactions | Implemented | `GET /supplier/v1/transactions` | Complete | Mostly ready | Browser QA for pagination/load-more | No for buyer beta | Yes |
| Payouts | Implemented | `POST/GET /supplier/v1/payout-requests` | Complete for manual payouts | Mostly ready | Browser QA for create/list/error handling | No for buyer beta | Yes |
| Supplier API key access | Implemented as paste-key MVP | Admin creates/regenerates key; no supplier self-key endpoint | Complete for admin-issued key | MVP ready | Clarify that key is admin-issued; do not build self-service key management without backend | No for buyer beta | Yes |
| Supplier settings | Not implemented | No supplier self-update endpoint | Not applicable | Not applicable | Do not build until backend exists | No | Yes |
| SMS Push | Implemented helper | `POST /supplier/v1/sms` | Complete | Mostly ready | Browser QA; ideally pair with activation history once implemented | Blocker for supplier sandbox manual testing | Yes for buyer beta |

## 4. Admin Screens

| Screen | Current status | Backend API | Backend readiness | Frontend readiness | Remaining UI work | Blocking? | Can postpone until beta? |
|---|---|---|---|---|---|---:|---:|
| Admin dashboard/Ops | Implemented | `GET /admin/ops/summary` | Complete | Mostly ready | Browser QA | Yes for operators | No |
| Supplier management | Implemented | `/admin/suppliers`, detail, patch, API key regenerate | Complete | Mostly ready | Browser QA for create/update/key one-time display | Yes for supplier sandbox | Yes for buyer beta |
| Supplier health | Implemented through inventory/retries/reliability | supplier inventory fields, release retries | Complete | Mostly ready | Browser QA for selected supplier context and visibility fields | Supplier sandbox useful | Yes |
| Supplier onboarding | Implemented admin-managed flow | supplier create/update/API key/regenerate | Complete | Mostly ready | Verify reservation config validation and copy; no self-service onboarding | Supplier sandbox blocker | Yes for buyer beta |
| Supplier payouts | Implemented | list/detail/approve/reject/mark-paid | Complete | Mostly ready | Browser QA for lifecycle actions and idempotent refresh | Supplier sandbox useful | Yes |
| Release retries | Implemented | `GET /admin/supplier-release-retries` | Complete | Mostly ready | Browser QA in Reliability tab | Supplier sandbox useful | Yes |
| Payment intents | Implemented | list/detail/manual-complete/reconciliation | Complete for `manual_test` | Mostly ready | Browser QA for manual complete and filters | Yes for manual funding ops | No |
| Users | Implemented list/basic views | users/status/limits; session revoke endpoint exists | Backend complete | Partial | Add UI/API client for `POST /admin/users/{user_id}/sessions/revoke-all`; verify status/limit controls if present | Beta useful security ops | Yes for tiny friendly beta |
| Session revoke | Missing in UI | `POST /admin/users/{user_id}/sessions/revoke-all` | Complete | Missing | Add admin client method and user action button/result count | Beta useful | Yes for tiny friendly beta |
| Audit logs | Implemented | `GET /admin/audit-logs` | Complete | Mostly ready | Browser QA and high-volume usability check | Beta useful | Yes |
| Request logs | Implemented | `GET /admin/api-request-logs` with filters | Complete | Mostly ready | Browser QA for request_id/method/status filters and copy button | Yes for support readiness | No |
| Risk actions | Implemented | risk users/detail/actions | Complete | Mostly ready | Browser QA for watch/note/clear/review | Beta useful | Yes |
| Operations/reliability | Implemented | ops summary, reconciliation, cleanup dry-run | Complete | Mostly ready | Browser QA for empty/error states | Yes for operators | No |
| Providers | Implemented basic admin list/create/update | `/admin/providers` | Complete for config rows | Mostly ready | Browser QA only; real provider ops are deferred until backend adapters exist | No | Yes |

## 5. API Mapping Checklist

| Area | Backend API exists? | Backend complete? | Needs frontend only? | Needs browser QA? |
|---|---:|---:|---:|---:|
| Buyer catalog/prices | Yes | Yes | No | Yes |
| Buyer order create/cancel/finish | Yes | Yes | No | Yes |
| Buyer wallet transactions | Yes | Yes | Mostly no | Yes |
| Buyer manual_test deposits | Yes | Yes for manual/local | Mostly no | Yes |
| Buyer managed API keys | Yes | Yes | Mostly no | Yes |
| Auth logout/logout-all | Yes | Yes | Yes | Yes |
| Supplier profile/inventory/payouts/SMS/transactions | Yes | Yes | Mostly no | Yes |
| Supplier activation history | Yes | Yes | Yes | Yes |
| Admin ops/risk/reliability/payments/payouts/logs | Yes | Yes | Mostly no | Yes |
| Admin session revoke-all | Yes | Yes | Yes | Yes |
| Real payment checkout | No usable real provider API | No | No | No |
| Real SMS provider operations | No real adapters | No | No | No |
| Supplier self-service onboarding/settings | No | No | No | No |

## 6. Implementation Priority

### Phase A: Critical Before RC-2

Goal: verify the already implemented frontend against existing backend behavior.

Status: complete. RC-2 browser QA is recorded in `docs/UI_READINESS_AUDIT.md`.

Tasks:

1. Run browser QA for `/`, `/buy`, `/dashboard`, `/orders`, `/deposit`, `/api-docs`, `/supplier`, and `/admin`.
2. Verify auth modal, protected-route redirects, token refresh, and logout behavior.
3. Confirm `/deposit` explains `manual_test` requires admin/manual completion.
4. Verify request logs, payment intents/manual completion, ops summary, and reliability pages load for admin.
5. Fix only blocking UI wiring or copy issues found by QA.

### Phase B: Closed Beta

Goal: make friendly-buyer support and basic operator actions smooth.

Tasks:

1. Wire frontend logout to `POST /auth/logout`.
2. Add current-user logout-all control if simple and clearly placed.
3. Add admin user session revoke-all control using existing backend endpoint.
4. Browser-test managed API key create/list/revoke/usage and wallet transaction history.
5. Browser-test manual_test funding runbook end to end with admin manual completion.

### Phase C: Supplier Sandbox

Goal: expose existing supplier backend visibility to sandbox suppliers and operators.

Tasks:

1. Add supplier activation history tab to `/supplier` using `GET /supplier/v1/activations`.
2. Add supplier activation history type and supplier API client method.
3. Browser-test supplier SMS push against returned activation ids.
4. Browser-test admin supplier onboarding/config/API-key issuance.
5. Browser-test supplier release retries and supplier payout lifecycle visibility.

### Phase D: Nice-To-Have

Goal: improve usability without changing backend scope.

Tasks:

1. Improve high-volume admin table pagination/filter usage where existing backend filters support it.
2. Add more contextual docs links to API/supplier/admin pages.
3. Polish dense dark-mode admin/supplier table readability during visual QA.
4. Improve empty/error states where browser QA finds confusing states.

## 7. UI Freeze Checklist

Absolutely must be finished:

- RC-2 browser QA recorded.
- Public/buyer navigation works.
- Auth modal opens from nav and buy flow.
- Protected pages redirect safely.
- Buyer can create an order with mock/manual systems.
- Buyer can create a `manual_test` payment intent and understand admin completion is required.
- Admin can manually complete a `manual_test` payment intent.
- Admin request logs show request_id and filters work.
- Admin ops/reliability pages load without crashes.
- Supplier cabinet accepts API key and loads profile/inventory/payout/SMS pages.
- Light/dark and mobile checks have no blocking unreadable or overlapping states.

Can safely wait:

- Supplier activation history UI, if RC-2 is buyer-only.
- Admin user session revoke-all UI, if beta is very small/trusted and backend endpoint is available for API use.
- Current-user logout-all UI.
- High-volume pagination polish.
- Buyer order event timeline, because buyer-safe backend endpoint does not exist yet.
- Real payment provider UX.
- Real SMS provider operations UI.
- Supplier self-service onboarding/settings.

## 8. Recommended First Frontend Task

RC-2 is complete. Next recommended frontend task: wire frontend logout to backend logout and add the admin target-user session revoke-all control, then implement supplier activation history UI before the first supplier sandbox.
