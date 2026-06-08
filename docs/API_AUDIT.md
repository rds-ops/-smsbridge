# API Audit

## 1. Executive Summary

Project state: the repository already has a working early MVP shape: Next.js frontend, FastAPI backend, PostgreSQL models with Alembic migrations, Redis-backed Celery worker, auth, admin panel API, buyer API, supplier API, wallet holds/captures/refunds, supplier inventory and supplier SMS push.

Main conclusion: the core direction is correct, but the marketplace core is still incomplete for a production 5sim-like service. The strongest parts are wallet transaction integrity, idempotent hold/capture/refund paths, buyer order idempotency, supplier API key auth, DB-backed supplier inventory reservation with row locks, order state/history, Redis-backed rate limiting, supplier reservation/release compensation, supplier payout request accounting skeleton, and payment intent accounting foundations including manual_test admin completion for local/dev simulation. The weakest parts are pricing/stock accuracy, missing real payment provider verification, missing real external payout provider integration, weak role model, real provider integrations, and provider webhook processing.

Critical issues before launch:

- Public/buyer price response exposes `provider_cost`; buyers should not see internal cost. DONE
- `/api/v1/services` and `/api/v1/countries` require JWT only, while `/api/v1/prices` allows JWT or API key. A real marketplace usually needs public catalog endpoints.
- Order creation with external providers reserves provider number before wallet hold. If wallet hold fails, provider number is not cancelled. DONE
- Supplier pool uses generated fake phone numbers instead of supplier-provided real numbers; current inventory is count-only. PARTIAL (supplier reservation callback supported; fake phone legacy/dev-only and blocked in production-like env)
- Supplier inventory decrement and wallet hold are transactional for supplier pool, but external provider stock is not decremented locally.
- Rate limiting is in process memory, not Redis, so it does not work correctly with multiple backend workers. DONE
- Admin seed uses known default credentials (`admin@smsbridge.local` / `change-me`) and Docker Compose uses `.env.example`. DONE (production safety guard blocks default secrets/passwords)
- Status fields are strings, not enums, and lifecycle transitions are only partially enforced. PARTIAL (order state machine + order_events exist; provider type/status validation added in admin schemas; DB enums not added)
- Payment intents, idempotent webhook wallet crediting, lifecycle visibility, and reconciliation visibility exist, but real payment provider verification/reconciliation is still missing. Supplier payout request accounting exists, but real external payout provider execution is not implemented. Formal stats/rate aggregation and provider webhook processing are still skeleton/incomplete.

## 2. Current Architecture Map

### Frontend

- Location: `apps/frontend`
- Framework: Next.js App Router.
- Pages found: landing, login, register, dashboard, buy, orders, order detail, settings, admin, API docs, terms/privacy/acceptable-use/abuse/developer-commands.
- API clients:
  - `apps/frontend/lib/shared/api.ts`: shared fetch/auth/token refresh logic.
  - `apps/frontend/lib/client/api.ts`: buyer API client.
  - `apps/frontend/lib/admin/api.ts`: admin API client.
- Localization:
  - `apps/frontend/lib/i18n/translations.ts`
  - `apps/frontend/lib/i18n.ts`
  - `apps/frontend/lib/i18n/useTranslation.tsx`

### Backend

- Location: `apps/backend/app`
- Framework: FastAPI.
- App entrypoint: `app/main.py`
- Routers:
  - `app/api/auth.py`: register/login/refresh/me.
  - `app/api/api_v1.py`: buyer/user API.
  - `app/api/admin.py`: admin management API.
  - `app/api/supplier.py`: supplier API.
- Models:
  - `app/models/entities.py`
- Schemas:
  - `app/schemas/auth.py`
  - `app/schemas/common.py`
  - `app/schemas/admin.py`
  - `app/schemas/supplier.py`
- Services:
  - `app/services/orders.py`
  - `app/services/wallet.py`
  - `app/services/suppliers.py`
  - `app/services/limits.py`
  - `app/services/audit.py`
- Provider adapters:
  - `app/providers/base.py`
  - `app/providers/mock.py`
  - `app/providers/five_sim.py`
  - `app/providers/sms_activate.py`
  - `app/providers/sms_man.py`
  - `app/providers/supplier_pool.py`
  - `app/providers/router.py`
- Core:
  - `app/core/config.py`
  - `app/core/deps.py`
  - `app/core/security.py`
  - `app/core/middleware.py`
  - `app/core/errors.py`
- Jobs:
  - `app/jobs/celery_app.py`
  - `app/jobs/tasks.py`
- DB:
  - `app/db/base.py`
  - `app/db/session.py`
  - `app/db/seed.py`
- Tests:
  - `app/tests/test_auth_admin.py`
  - `app/tests/test_order_wallet.py`
  - `app/tests/test_suppliers.py`
  - `app/tests/test_celery_registration.py`

### Database

- PostgreSQL via SQLAlchemy ORM.
- Alembic migrations exist:
  - `0001_initial.py`
  - `0002_supplier_module.py`
- Seed script creates admin, demo user, mock provider, supplier pool provider, services, countries, prices, and system settings.

### Redis

- Configured through `settings.redis_url`.
- Used as Celery broker and result backend.
- Used for distributed API rate limiting counters (fail-open) and Celery broker/backend.
- Not used for idempotency keys, durable business state, or distributed locks beyond DB row locks and Celery.

### Docker

- `docker-compose.yml` services:
  - `postgres`
  - `redis`
  - `backend`
  - `worker`
  - `frontend`
  - `adminer`
- Backend command runs migrations, seed, then Uvicorn.
- Worker runs Celery worker with beat in the same process.

### Responsibility Separation

What is good:

- Provider adapters are isolated under `apps/backend/app/providers`.
- Wallet logic is in `services/wallet.py`.
- Order lifecycle logic is mostly in `services/orders.py`.
- Supplier inventory/SMS/reward logic is mostly in `services/suppliers.py`.
- Auth dependencies are centralized in `core/deps.py`.

What is mixed:

- Routers still do direct ORM reads and updates for many admin/list endpoints.
- No repository layer exists; DB access is inside routers and services.
- Status transition logic is not centralized as an explicit state machine.
- Pricing sync and supplier inventory logic are coupled in `services/suppliers.py`.

## 3. Current Endpoint Inventory

| Method | Path | Router/File | Role | Purpose | Risk/Comment |
|---|---|---|---|---|---|
| GET | `/health` | `app/main.py` | public | Health check | OK. |
| POST | `/auth/register` | `app/api/auth.py` | public auth | Create user, wallet and default limits | No email normalization validation beyond lowercasing; no email verification; no brute-force/abuse control beyond global Redis IP rate limit. |
| POST | `/auth/login` | `app/api/auth.py` | public auth | Password login, returns access/refresh tokens | No lockout/backoff; logs request path only, not body. |
| POST | `/auth/refresh` | `app/api/auth.py` | auth | Refresh access/refresh pair | Refresh tokens are stateless; no revocation table/session model. |
| GET | `/auth/me` | `app/api/auth.py` | auth | Current user profile | OK. |
| GET | `/api/v1/balance` | `app/api/api_v1.py` | buyer/API key | Return wallet balance/held balance | OK, but only current wallet, no transaction history endpoint. |
| GET | `/api/v1/services` | `app/api/api_v1.py` | buyer JWT | Active services | Should probably be public or public catalog. API key is not accepted here while other buyer API endpoints accept it. |
| GET | `/api/v1/countries` | `app/api/api_v1.py` | buyer JWT | Active countries | Same issue as services. |
| GET | `/api/v1/prices` | `app/api/api_v1.py` | buyer/API key | List prices filtered by service/country | Buyer schema exposes `final_price`, not `provider_cost`. |
| POST | `/api/v1/orders` | `app/api/api_v1.py` | buyer/API key | Buy/reserve number and hold wallet funds | Uses explicit transactional wrapper and optional `Idempotency-Key`; wallet hold happens before external provider reservation. |
| GET | `/api/v1/orders` | `app/api/api_v1.py` | buyer JWT | List own orders | API key not accepted here, inconsistent with get order/create/cancel/finish. |
| GET | `/api/v1/orders/{public_id}` | `app/api/api_v1.py` | buyer/API key | Fetch own order | Ownership enforced. |
| POST | `/api/v1/orders/{public_id}/cancel` | `app/api/api_v1.py` | buyer/API key | Cancel order and refund hold | Idempotent for cancelled/expired/refunded. |
| POST | `/api/v1/orders/{public_id}/finish` | `app/api/api_v1.py` | buyer/API key | Finish after SMS and capture hold | Idempotent for completed. |
| POST | `/api/v1/api-key/regenerate` | `app/api/api_v1.py` | buyer JWT | Regenerate buyer API key | OK; old key invalidated. No key label/rotation history. |
| GET | `/api/v1/limits` | `app/api/api_v1.py` | buyer/API key | Return user limits | OK. |
| GET | `/admin/users` | `app/api/admin.py` | admin | List users | Limit 200 only; no pagination/filtering. |
| GET | `/admin/users/{user_id}` | `app/api/admin.py` | admin | User detail | OK. |
| PATCH | `/admin/users/{user_id}/status` | `app/api/admin.py` | admin | Update user status | Audit logged. |
| PATCH | `/admin/users/{user_id}/limits` | `app/api/admin.py` | admin | Update tier/limits | Audit logged. |
| GET | `/admin/orders` | `app/api/admin.py` | admin | List orders | Limit 200 only; no pagination/filtering. |
| GET | `/admin/orders/{order_id}` | `app/api/admin.py` | admin | Order detail | Uses internal numeric id. OK for admin. |
| GET | `/admin/providers` | `app/api/admin.py` | admin | List providers | OK. |
| POST | `/admin/providers` | `app/api/admin.py` | admin | Create provider | Does not accept/store provider API key; real provider setup incomplete. |
| PATCH | `/admin/providers/{provider_id}` | `app/api/admin.py` | admin | Update provider | Does not handle secret rotation. |
| GET | `/admin/suppliers` | `app/api/admin.py` | admin | List suppliers with inventory count | OK. |
| POST | `/admin/suppliers` | `app/api/admin.py` | admin | Create supplier | OK. |
| GET | `/admin/suppliers/{supplier_id}` | `app/api/admin.py` | admin | Supplier detail | OK. |
| PATCH | `/admin/suppliers/{supplier_id}` | `app/api/admin.py` | admin | Update supplier | OK. |
| POST | `/admin/suppliers/{supplier_id}/api-key/regenerate` | `app/api/admin.py` | admin | Generate supplier API key | OK; old key invalidated. |
| GET | `/admin/suppliers/{supplier_id}/inventory` | `app/api/admin.py` | admin | Supplier inventory | OK. |
| GET | `/admin/suppliers/{supplier_id}/activations` | `app/api/admin.py` | admin | Supplier activations | OK. |
| GET | `/admin/suppliers/{supplier_id}/sms` | `app/api/admin.py` | admin | Supplier SMS records | OK, sensitive content; admin only. |
| GET | `/admin/suppliers/{supplier_id}/transactions` | `app/api/admin.py` | admin | Supplier transaction ledger | OK. |
| POST | `/admin/suppliers/{supplier_id}/adjustment` | `app/api/admin.py` | admin | Manual supplier balance adjustment | Creates transaction, prevents negative supplier balance. |
| GET | `/admin/supplier-payout-requests` | `app/api/admin.py` | admin | List supplier payout requests | Skeleton only; no external payout provider. |
| GET | `/admin/supplier-payout-requests/{id}` | `app/api/admin.py` | admin | Supplier payout request detail | Admin-only operational view. |
| POST | `/admin/supplier-payout-requests/{id}/approve` | `app/api/admin.py` | admin | Approve supplier payout request | Status-only approval; held funds remain held. |
| POST | `/admin/supplier-payout-requests/{id}/reject` | `app/api/admin.py` | admin | Reject supplier payout request | Releases held funds back to supplier balance and writes ledger. |
| POST | `/admin/supplier-payout-requests/{id}/mark-paid` | `app/api/admin.py` | admin | Mark supplier payout paid | Decreases supplier held balance and writes ledger; no external money sent. |
| POST | `/admin/wallets/deposit` | `app/api/admin.py` | admin | Manual user deposit | Creates wallet transaction. No payment provider integration. |
| POST | `/admin/wallets/adjustment` | `app/api/admin.py` | admin | Manual user wallet adjustment | Creates wallet transaction, prevents negative balance. |
| POST | `/admin/orders/{order_id}/refund` | `app/api/admin.py` | admin | Refund order | Idempotent for refunded/expired/cancelled. Can attempt refund after completed and fail in wallet if captured. |
| GET | `/admin/audit-logs` | `app/api/admin.py` | admin | List audit logs | Limit 200 only. |
| GET | `/admin/api-request-logs` | `app/api/admin.py` | admin | List request logs | Includes buyer/admin/auth/supplier/internal provider webhook metadata; no request bodies. |
| GET | `/admin/metrics` | `app/api/admin.py` | admin | Basic daily metrics | Gross profit subtracts provider cost but not supplier rewards consistently; no time zone/accounting period abstraction. |
| GET | `/supplier/v1/me` | `app/api/supplier.py` | supplier | Supplier profile | API key auth. |
| GET | `/supplier/v1/inventory` | `app/api/supplier.py` | supplier | Supplier inventory list | OK. |
| POST | `/supplier/v1/inventory/update` | `app/api/supplier.py` | supplier active | Upsert count-based inventory | No real phone-number inventory; no idempotency key; max 500 items. |
| POST | `/supplier/v1/payout-requests` | `app/api/supplier.py` | supplier active | Request payout from supplier balance | Moves balance to held balance and writes `payout_hold`; no external payout provider. |
| GET | `/supplier/v1/payout-requests` | `app/api/supplier.py` | supplier | List own payout requests | Supplier-scoped. |
| POST | `/supplier/v1/sms` | `app/api/supplier.py` | supplier active | Push SMS for activation/phone | Idempotent by supplier SMS id. Does not require activation id if phone matches active activation. |

Dangerous or wrongly exposed endpoints/fields:

- `/api/v1/prices` no longer exposes `provider_cost`; buyer/admin price schemas are separated.
- `/api/v1/services`, `/api/v1/countries`, `/api/v1/orders` list are JWT-only while other API endpoints accept API keys. This is inconsistent for developer API usage.
- `/admin/metrics` is admin-only, but its financial math is not production accounting.
- Supplier endpoints are included in API request logging. DONE
- `/internal/provider-webhooks/{provider_code}` exists as a skeleton, but does not process real provider webhook payloads yet.

## 4. Current Database Model Inventory

| Model/Table | Purpose | Key Fields | Relations | Issues |
|---|---|---|---|---|
| `User` / `users` | Buyer/admin accounts | `email`, `password_hash`, `role`, `status`, `tier`, `api_key_hash`, `locale` | One-to-one `UserLimit`, `Wallet`; referenced by `Order`, `WalletTransaction`, `AuditLog`, `ApiRequestLog` | `role`/`status` are strings, no enum/check constraint. No failed login/session/revoked token table. |
| `UserLimit` / `user_limits` | Per-user order/spend limits | `max_orders_per_minute`, `max_orders_per_day`, `max_active_orders`, `max_daily_spend` | FK `user_id` unique | Good MVP table. Limits are enforced by DB counts, not Redis counters. |
| `Wallet` / `wallets` | User available and held balance | `balance`, `held_balance`, `currency` | FK `user_id` unique | Non-negative balance/held balance DB checks exist. |
| `WalletTransaction` / `wallet_transactions` | Wallet ledger | `user_id`, `order_id`, `payment_intent_id`, `type`, `amount`, `status`, `reference`, `metadata`, `created_at` | FK user/order/payment intent | Good ledger base. Unique `(order_id,type,status)` makes hold/capture/refund idempotent; unique non-null `payment_intent_id` makes payment intent deposits idempotent. Manual deposit/adjustment with no order/payment intent are not idempotent. No enum/check constraints. |
| `Provider` / `providers` | External provider config | `code`, `type`, `status`, `priority`, `base_url`, `api_key_encrypted`, `default_markup_percent` | Referenced by `Price`, `Order` | `api_key_encrypted` exists but no encryption implementation found in current codebase. Provider adapters are placeholders except mock/supplier pool. |
| `Service` / `services` | Product/service catalog | `code`, `name_ru`, `name_en`, `category`, `is_active` | Referenced by code in prices/orders/inventory | No FK from `Price.service_code`, `Order.service_code`, `SupplierInventory.service_code`; referential integrity depends on service code validation. |
| `Country` / `countries` | Country catalog | `iso2`, `name_ru`, `name_en`, `is_active` | Referenced by code in prices/orders/inventory | No FK from country code columns. |
| `Price` / `prices` | Provider price and available count by service/country/operator | `provider_id`, `service_code`, `country_iso2`, `operator`, `provider_cost`, `final_price`, `available_count`, `delivery_rate` | FK provider | Nullable `operator` uniqueness is normalized by `operator_key`. No FK to service/country. Buyer schema hides provider cost. |
| `Order` / `orders` | Buyer activation order | `public_id`, `user_id`, `provider_id`, `provider_order_id`, `service_code`, `country_iso2`, `operator`, `phone_number`, `status`, `price`, `provider_cost`, `sms_code`, `sms_text`, `expires_at` | FK user/provider; one supplier activation optional | State transitions are centralized and logged in `order_events`. No `completed_at`, `cancelled_at`, `refunded_at`, `sms_received_at`, `last_polled_at`, `error_code`. |
| `AuditLog` / `audit_logs` | Admin/system audit events | `actor_user_id`, `action`, `entity_type`, `entity_id`, `metadata` | FK user nullable | OK base. No actor supplier id. |
| `ApiRequestLog` / `api_request_logs` | API request logs | `user_id`, `supplier_id`, `endpoint`, `method`, `ip_address`, `status_code` | FK user/supplier nullable | Supplier endpoints are logged. No duration/user agent. |
| `SystemSetting` / `system_settings` | JSON settings | `key`, `value` | None | OK for small settings. |
| `Supplier` / `suppliers` | Supplier account/entity | `name`, `email`, `status`, `api_key_hash`, `reward_percent`, `balance`, `held_balance`, `currency` | Referenced by supplier inventory/activation/sms/transactions/payout requests | No user linkage. No supplier wallet transaction check constraint. No KYC/moderation fields. |
| `SupplierInventory` / `supplier_inventory` | Count-based supplier stock by service/country/operator | `supplier_id`, `service_code`, `country_iso2`, `operator`, `available_count`, visibility fields, `status`, `last_sync_at` | FK supplier | No exact real number pool. Nullable `operator` uniqueness is normalized by `operator_key`. No FK to service/country. |
| `SupplierActivation` / `supplier_activations` | Reserved supplier order mapping | `supplier_id`, `order_id`, `supplier_activation_id`, `phone_number`, `status`, `client_price`, `supplier_reward`, `sms_text`, `sms_code` | FK supplier/order | `order_id` unique. No unique active phone reservation constraint. Reservation-enabled suppliers return real numbers; fake phone is legacy/dev-only and blocked in production-like environments. |
| `SupplierSms` / `supplier_sms` | SMS messages pushed by supplier | `supplier_id`, `activation_id`, `order_id`, `supplier_sms_id`, `phone_number`, `phone_from`, `text`, `status` | FK supplier/activation/order | Idempotent by supplier SMS id. No parsed code confidence/source metadata. |
| `SupplierTransaction` / `supplier_transactions` | Supplier ledger | `supplier_id`, `activation_id`, `order_id`, `type`, `amount`, `status`, `reference`, `metadata` | FK supplier/activation/order | Reward idempotency exists. Payout hold/release/paid ledger entries exist. Supplier balance DB checks exist. |
| `SupplierReleaseRetry` / `supplier_release_retries` | Durable retry queue for failed supplier release callbacks | `supplier_activation_id`, `supplier_id`, `order_id`, `status`, `attempt_count`, `next_retry_at`, `last_error` | FK supplier/activation/order | Release retry queue exists with capped retries; no separate UI yet. |
| `SupplierPayoutRequest` / `supplier_payout_requests` | Supplier payout lifecycle skeleton | `public_id`, `supplier_id`, `amount`, `currency`, `status`, payout details, admin/failure notes, lifecycle timestamps | FK supplier | Internal accounting only. External payout provider integration, KYC, payout reconciliation and real provider status webhooks are not implemented. |

Missing or incomplete tables/fields:

- `payment_methods` or provider-specific deposit records for real user top-ups.
- External payout provider transfer records/status webhooks.
- Exact supplier phone-number inventory table.
- `provider_price_snapshots` or `price_sync_runs`.
- `supplier_number_inventory` if suppliers provide exact phone numbers instead of only counts.
- `idempotency_keys` for payment callbacks (buyer order creation exists).
- `sessions` / `refresh_tokens` / token revocation.
- `roles` / `permissions` if more roles than `user` and `admin` are needed.
- `operator` catalog/table if operators must be normalized.
- `country_service_operator_supplier_stats` or materialized stats table.

## 5. Business Logic Review

### Pricing

How it is now:

- `Price` stores `provider_cost`, `final_price`, `available_count`, and `delivery_rate`.
- `providers/router.py::final_price()` calculates `provider_cost * (1 + markup_percent / 100)`.
- Seed creates mock prices with provider markup.
- Supplier pool price is generated in `services/suppliers.py::sync_supplier_pool_price()`: it takes the cheapest active non-supplier-pool `Price.final_price` as reference and sets supplier `provider_cost` to 70% of that final price.
- Supplier reward is calculated at reservation time as `order.price * supplier.reward_percent / 100`.

What is normal:

- Storing final customer price on the order is correct; it freezes the purchased price.
- Storing provider/supplier cost on the order is useful for margin reporting.
- Keeping provider adapters isolated is correct.

What is risky:

- Pricing is stored, not computed from a clear pricing policy table. There is no explicit per-service/country markup override.
- Supplier pool pricing depends on external/mock provider prices and hardcoded default `0.5000` fallback.
- `Price` does not FK service/country, so stale code values can exist.
- No price sync job found in current codebase except supplier pool price update during supplier inventory update.

Needed changes:

- Add pricing policy model: global markup, provider markup, service/country/operator overrides, min price, rounding.
- Add provider price sync jobs and price freshness metadata.
- Add internal/admin-only price detail endpoint that includes cost/margin.

### Stock/count

How it is now:

- External/mock provider stock lives in `prices.available_count`.
- Supplier stock lives in `supplier_inventory.available_count`.
- Supplier pool `Price.available_count` is sum of active supplier inventory rows.
- Supplier pool reservation decrements selected `SupplierInventory.available_count`.

What is normal:

- Aggregated stock by service/country/operator is a reasonable MVP.
- Supplier inventory selection uses `with_for_update()`, which helps prevent concurrent decrements of the same row.

What is risky:

- External provider `Price.available_count` is not decremented on order creation.
- Supplier pool aggregate `Price.available_count` can become stale and has nullable-operator uniqueness risk.
- Count-only stock means the system cannot guarantee that a real phone number exists unless the supplier returns/provides one.
- No stock freshness/TTL rules. Old supplier inventory can remain active forever.

Needed changes:

- Add `last_sync_at` and freshness checks for all provider prices/stock.
- For external providers, either decrement local cached stock on reservation or treat `available_count` as advisory only and hide exact counts.
- For suppliers, decide between count-only API and exact-number inventory. If exact numbers are needed, add `supplier_numbers` table.
- Add periodic reconciliation job for supplier pool aggregate prices.

### Order Creation

How it is now:

- `POST /api/v1/orders` calls `order_service.create_order()`.
- It validates service/country, gets candidate prices ordered by provider priority desc and final price asc.
- It enforces user limits before each provider attempt.
- Supplier pool path creates order, reserves supplier activation, then holds wallet funds.
- External provider path calls provider `get_number()`, creates order, then holds wallet funds.

What is normal:

- Candidate provider fallback exists.
- User limits and wallet hold are enforced in service layer.
- Order stores price and provider cost at purchase time.

What is risky:

- External provider local `prices.available_count` is not decremented after purchase.
- Exact supplier phone-number inventory is not implemented.
- Real provider adapters remain placeholders.

Needed changes:

- Add real provider stock sync/freshness and reconciliation.
- Add exact phone inventory if the product must control supplier numbers platform-side.
- Add provider error fields if support/debugging needs structured reservation failure reasons.

### Number Reservation

How it is now:

- External providers return a phone number from adapter.
- Supplier pool selects a supplier inventory row with positive count and row-locks it.
- Reservation-enabled suppliers are called through the supplier reservation callback and return a real phone number and supplier activation id.
- `_fake_supplier_phone()` remains only as a legacy/dev-only fallback and is blocked in production-like environments.

What is normal:

- DB row lock for supplier inventory is the correct direction.
- Supplier activation maps one order to one supplier activation.

What is risky:

- Fake supplier phone numbers mean supplier pool is not real marketplace inventory yet.
- No unique active reservation constraint on phone number.
- Count-only supplier inventory cannot prevent the same real number from being used twice by the supplier outside this system.
- Unique constraints with nullable `operator` can allow duplicates in PostgreSQL.

Needed changes:

- Add exact phone number reservation flow or require supplier to return a phone number during reservation.
- Add unique active-number constraints where possible.
- Use partial unique indexes or normalized `operator_key = 'any'` instead of nullable operator in unique keys.

### SMS Receiving

How it is now:

- External providers are polled by Celery `poll_waiting_orders()`.
- Supplier SMS is pushed to `POST /supplier/v1/sms`.
- SMS code is extracted with regex for 4-8 digits.
- Supplier SMS is idempotent by `(supplier_id, supplier_sms_id)`.

What is normal:

- Supplier SMS push path is a good MVP.
- SMS is persisted in `supplier_sms` and denormalized onto order.

What is risky:

- `/internal/provider-webhooks/{provider_code}` is a skeleton only and does not process real provider events yet.
- Real provider webhook payload validation/storage is not implemented.
- Supplier can push SMS by phone number without activation id; this can attach to latest active activation for that phone.

Needed changes:

- Implement real provider webhook payload validation and route to `sms_messages` / `transition_order`.
- Prefer activation id for supplier SMS; phone fallback should be strict and audited.

### Order Lifecycle

How it is now:

- Main statuses used: `created`, `waiting_sms`, `sms_received`, `completed`, `cancelled`, `expired`, `failed`, `refunded`.
- Cancel is idempotent for `cancelled`, `expired`, `refunded`; blocked after `completed`/`failed`.
- Finish is idempotent for `completed`; allowed only from `sms_received`.
- Polling expires waiting orders and refunds wallet hold.

What is normal:

- Basic lifecycle is recognizable and tests cover core wallet behavior.
- Capture and refund paths are idempotent through wallet transaction checks.

What is risky:

- Statuses are plain strings with no enum/check constraint.
- There is no state transition table/function.
- Admin refund calls `refund_order()` for any non-refunded/non-expired/non-cancelled order; for completed orders wallet layer rejects because capture exists. This is safe but awkward.
- No `completed_at`, `cancelled_at`, `expired_at`, `refunded_at` timestamps.
- Celery polling selects 100 waiting orders every 5 seconds without row locking/skip locked; multiple workers could process same rows.

Needed changes:

- Add centralized state machine and transition audit.
- Add status timestamp fields or order events table.
- Use `SELECT ... FOR UPDATE SKIP LOCKED` in polling job.
- Add explicit admin refund policy for completed orders if post-completion refunds are allowed.

### Balance/payment

How it is now:

- Wallet has `balance` and `held_balance`.
- Every wallet movement creates `WalletTransaction`.
- `hold`, `capture`, and `refund` are idempotent per order/type/status.
- Admin can deposit and adjust manually.

What is normal:

- Wallet row is locked with `with_for_update()`.
- Negative user balance/held balance is prevented in service layer.
- Holds are created on order purchase, captures on finish, refunds on cancel/expire.

What is risky:

- No DB check constraints for non-negative balances.
- Payment intent state model exists for `manual_test` local/dev simulation, but no real payment provider integration or provider signature verification exists.
- Manual deposit has no idempotency. Duplicate admin request can double-credit.
- `spent_today` uses hold transactions, so refunded orders still count toward daily spend.

Needed changes:

- Add DB check constraints for `balance >= 0` and `held_balance >= 0`.
- Add deposit/payment tables with provider references and idempotency.
- Add wallet transaction list endpoint for users.
- Decide whether refunded holds count toward daily spend.

### Supplier payout

How it is now:

- Supplier has `balance` and `held_balance`.
- On buyer finish, `complete_supplier_reward()` credits supplier balance and creates `SupplierTransaction(type='reward')`.
- Admin can manually adjust supplier balance.

What is normal:

- Supplier reward is idempotent by unique supplier/order/type/status.
- Supplier balance is locked before reward credit.

What is risky:

- Supplier payout requests exist, including payout holds, admin approval, reject release, and mark-paid ledger entries.
- Supplier reward uses current supplier reward percent in transaction metadata but activation reward was calculated earlier; this is mostly OK, but metadata can be confusing if percent changed.
- `held_balance` is used for pending payout holds.
- No minimum payout, KYC, real payout account verification, external provider execution, or payout reconciliation exists yet.

Needed changes:

- Add real external payout provider integration and reconciliation.
- Add payout account verification/KYC and minimum payout policy.
- Add provider status callbacks or operator reconciliation for paid/failed external transfers.

### Rate/statistics

How it is now:

- `SupplierInventory.success_rate` can be supplied by supplier.
- Supplier pool `Price.delivery_rate` is average of supplier-provided success rates.
- Admin metrics counts daily orders and sums wallet/provider/supplier numbers.

What is normal:

- Some success-rate fields exist.

What is risky:

- Success rate is self-reported by supplier, not calculated from actual completed/failed/expired activations.
- No stats by `country/product/operator/supplier`.
- No delayed SMS time calculation from actual events.
- No provider-level quality scoring beyond priority and price.

Needed changes:

- Add calculated stats table or materialized query for service/country/operator/supplier/provider.
- Track counts: reserved, sms_received, completed, cancelled, expired, failed, average SMS time.
- Use stats in supplier/provider selection instead of self-reported success only.

## 6. Security Review

Problems and recommendations:

- JWT secret default is `change-this-secret`; Docker Compose uses `.env.example`. Production must fail startup if secret is default.
- Seed creates admin with known password `change-me`. This must be disabled in production or require first-run password injection.
- User roles are only `user` and `admin`; supplier auth is separate API key entity. This is OK for MVP, but permissions are coarse.
- User `status` is checked for order creation only. `get_current_user()` does not block suspended users from all authenticated reads.
- Supplier API keys are hashed, which is good. Provider API key encryption is only a field; encryption/decryption not found in current codebase.
- Password hashing uses `pbkdf2_sha256`; acceptable for MVP, but Argon2id or bcrypt would be stronger.
- Login has no account lockout, CAPTCHA, or per-account throttle.
- Rate limit uses Redis counters (fail-open) and is applied as middleware. It is IP-based and still needs proxy header hardening for real deployments.
- CORS is configurable and currently defaults to `http://localhost:3000`, OK for local.
- Request logging does not log request bodies, which avoids many sensitive data leaks. Supplier endpoints are included and supplier_id is logged when auth succeeds. DONE
- Buyer price schema leaks `provider_cost`. Remove from buyer/public schemas. DONE
- Admin endpoints are protected by `require_admin`, good.
- Supplier endpoints are protected by supplier API key and active supplier checks on write endpoints, good.
- No CSRF issue for API bearer tokens in normal usage, but frontend token storage should be reviewed. Frontend uses browser storage logic in `shared/api.ts`; exact storage security should be audited separately.
- Provider type/status validation exists in admin schemas. DONE
- DB check constraints exist for wallet/supplier balances (non-negative). DONE
- No audit log for buyer API key regeneration.
- Internal provider webhook namespace exists but is skeleton-only and uses shared-secret auth; no signature validation yet. PARTIAL

## 7. Missing Features for MVP (Audit Status)

| Feature | Priority | Why needed | Suggested endpoint/model/service | Status |
|---|---|---|---|---|
| Hide provider costs from buyer/public API | P0 | Prevent margin leakage | Buyer price schema without `provider_cost`; admin schema keeps it | DONE |
| Safe order purchase transaction/idempotency | P0 | Prevent double purchase and provider reservation leaks | `IdempotencyKey` model; transactional wrapper | DONE |
| Real supplier number reservation | P0 | Current supplier pool generates fake phone numbers | Supplier reservation callback integration | PARTIAL (callback implemented; exact inventory not implemented) |
| Explicit order state machine | P0 | Prevent invalid transitions and make lifecycle auditable | `services/order_state.py`, `order_events` model | DONE |
| Redis/distributed rate limiting | P0 | In-memory limiter breaks under multiple workers | `services/rate_limit.py` using Redis | DONE |
| DB money check constraints | P0 | Defense in depth for wallet/supplier balances | CHECK constraints for non-negative balances/held balances | DONE |
| Payment/deposit model | P0 | Manual admin deposit is not enough for launch | `payment_intents`, `/internal/payment-webhooks/{provider}`, `/admin/payment-intents/{id}/manual-complete` | PARTIAL (intent model/API, idempotent webhook wallet crediting, admin manual_test completion, lifecycle/reconciliation visibility exist; real provider verification/reconciliation not implemented) |
| Provider price/stock sync | P0 | Prices and counts must be fresh | Celery tasks, sync runs | NOT DONE |
| Generic SMS message table | P0 | External provider SMS should be stored consistently | `sms_messages` + idempotent inserts | DONE |
| Internal webhook namespace | P0 | Providers/payment callbacks need isolated auth | `/internal/provider-webhooks/{provider_code}` | PARTIAL (skeleton only) |
| Supplier release retry queue | P0 | Failed supplier release callbacks can leave numbers reserved | `supplier_release_retries`, Celery retry task | DONE |
| Supplier payout lifecycle | P1 | Suppliers need withdrawals and accounting | `supplier_payout_requests`, `/supplier/v1/payout-requests`, `/admin/supplier-payout-requests` | PARTIAL (request/hold/admin approve/reject/mark-paid ledger skeleton; no external payout provider) |
| Supplier/provider stats | P1 | Needed for routing quality and marketplace health | `supplier_stats`, `provider_stats`, stats job | NOT DONE |
| Pagination/filtering | P1 | Admin and order lists cap at fixed 100/200/500 | Cursor pagination schemas | NOT DONE |
| User wallet transaction history | P1 | Buyers need account transparency | `/buyer/wallet/transactions` or `/api/v1/wallet/transactions` | NOT DONE |
| API key management with multiple keys | P1 | Safe rotation without downtime | `api_keys` table with labels/scopes/last_used_at | NOT DONE |
| Refresh token/session revocation | P1 | Logout and compromised token handling | `sessions`/`refresh_tokens` table | NOT DONE |
| Operator catalog | P1 | Normalize operator names and availability | `operators` table | NOT DONE |
| Provider secret encryption | P1 | Required before real provider credentials | `core/secrets.py`, KMS/Fernet integration | NOT DONE |
| Admin moderation queue | P1 | Supplier onboarding and abuse review | `/admin/moderation/*`, supplier status events | NOT DONE |
| Full audit coverage | P1 | Track API key changes, supplier writes, financial ops | extend `AuditLog`, supplier actor support |
| Public catalog endpoints | P2 | Better unauthenticated discovery | `/public/services`, `/public/countries`, `/public/prices` |
| OpenAPI/API docs polish | P2 | Developer usability | versioned API docs and examples |

## 8. Recommended API Structure

Recommended MVP namespaces:

### `/auth`

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`

### `/public`

- `GET /public/services`
- `GET /public/countries`
- `GET /public/operators?country=...`
- `GET /public/prices?service=...&country=...&operator=...`
- `GET /public/health`

Public price response must include customer price and availability only, not provider cost.

### `/buyer` or versioned `/api/v1`

Keep `/api/v1` if external developers already use it, but internally map it as buyer API.

- `GET /api/v1/balance`
- `GET /api/v1/wallet/transactions`
- `GET /api/v1/limits`
- `GET /api/v1/prices`
- `POST /api/v1/orders`
- `GET /api/v1/orders`
- `GET /api/v1/orders/{public_id}`
- `POST /api/v1/orders/{public_id}/cancel`
- `POST /api/v1/orders/{public_id}/finish`
- `POST /api/v1/api-keys`
- `GET /api/v1/api-keys`
- `DELETE /api/v1/api-keys/{key_id}`
- `POST /api/v1/payments/deposit`
- `GET /api/v1/payments`

### `/supplier`

- `GET /supplier/v1/me`
- `GET /supplier/v1/inventory`
- `POST /supplier/v1/inventory/update`
- `POST /supplier/v1/reservations/{reservation_id}/accept` if suppliers allocate real numbers on demand
- `POST /supplier/v1/sms`
- `GET /supplier/v1/activations`
- `GET /supplier/v1/transactions`
- `POST /supplier/v1/payout-requests`
- `GET /supplier/v1/payout-requests`

### `/admin`

- `GET /admin/metrics`
- `GET /admin/users`
- `GET /admin/users/{id}`
- `PATCH /admin/users/{id}/status`
- `PATCH /admin/users/{id}/limits`
- `GET /admin/orders`
- `GET /admin/orders/{id}`
- `POST /admin/orders/{id}/refund`
- `GET /admin/providers`
- `POST /admin/providers`
- `PATCH /admin/providers/{id}`
- `POST /admin/providers/{id}/api-key`
- `POST /admin/providers/{id}/sync`
- `GET /admin/prices`
- `GET /admin/suppliers`
- `POST /admin/suppliers`
- `GET /admin/suppliers/{id}`
- `PATCH /admin/suppliers/{id}`
- `POST /admin/suppliers/{id}/api-key/regenerate`
- `GET /admin/suppliers/{id}/inventory`
- `GET /admin/suppliers/{id}/activations`
- `GET /admin/suppliers/{id}/sms`
- `GET /admin/suppliers/{id}/transactions`
- `POST /admin/suppliers/{id}/adjustment`
- `GET /admin/supplier-payout-requests`
- `GET /admin/supplier-payout-requests/{id}`
- `POST /admin/supplier-payout-requests/{id}/approve`
- `POST /admin/supplier-payout-requests/{id}/reject`
- `POST /admin/supplier-payout-requests/{id}/mark-paid`
- `GET /admin/audit-logs`
- `GET /admin/api-request-logs`

### `/internal`

- `POST /internal/providers/{provider_code}/sms`
- `POST /internal/providers/{provider_code}/status`
- `POST /internal/payments/{provider_code}/webhook`
- `POST /internal/jobs/reconcile-wallets`
- `POST /internal/jobs/reconcile-supplier-balances`

Internal endpoints should require HMAC signatures, mTLS, private network access, or another explicit internal auth mechanism. They should not use buyer JWT auth.

## 9. Recommended Backend Structure

Current structure is close, but for growth use clearer boundaries:

```text
app/
  api/
    v1/
      auth.py
      public.py
      buyer.py
      supplier.py
      admin.py
      internal.py
    deps.py
  schemas/
    auth.py
    public.py
    buyer.py
    supplier.py
    admin.py
    internal.py
    common.py
  models/
    user.py
    wallet.py
    catalog.py
    provider.py
    order.py
    supplier.py
    payment.py
    audit.py
  services/
    orders.py
    order_state.py
    pricing.py
    stock.py
    wallet.py
    payments.py
    suppliers.py
    supplier_payouts.py
    provider_sync.py
    messages.py
    stats.py
    limits.py
    audit.py
  repositories/
    users.py
    wallets.py
    orders.py
    prices.py
    suppliers.py
    payments.py
  providers/
    base.py
    router.py
    five_sim.py
    sms_activate.py
    sms_man.py
    mock.py
    supplier_pool.py
  core/
    config.py
    security.py
    permissions.py
    middleware.py
    errors.py
    secrets.py
  db/
    base.py
    session.py
    seed.py
  workers/
    celery_app.py
    schedules.py
  tasks/
    poll_orders.py
    sync_prices.py
    expire_orders.py
    stats.py
```

What should live where:

- `api/`: HTTP routing only. Validate request/response, call service methods, no complex business logic.
- `schemas/`: Pydantic input/output models. Keep buyer/public/admin schemas separate to avoid leaking fields.
- `models/`: SQLAlchemy tables only. Split large `entities.py` once it becomes hard to navigate.
- `services/`: business rules, transactions, state transitions, pricing, stock, wallet and payout logic.
- `repositories/`: reusable DB queries and locking patterns. This keeps routers/services from duplicating ORM queries.
- `core/`: config, security, permissions, errors, middleware, secret encryption.
- `db/`: database session/base/seed helpers.
- `workers/` and `tasks/`: Celery config and task modules. Keep task functions thin; they should call services.

## 10. Immediate Next Steps

Recommended 1-2 week plan:

1. P0 security/API cleanup:
   - Remove `provider_cost` from buyer/public price response. DONE
   - Add production startup guard for default `SECRET_KEY` and default seeded admin password. DONE
   - Include supplier endpoints in request logging or add supplier request log fields. DONE
   - Validate provider type/status values with allowed values. DONE

2. P0 wallet/order safety:
   - Add DB check constraints for non-negative `wallets.balance`, `wallets.held_balance`, `suppliers.balance`, `suppliers.held_balance`. DONE
   - Add explicit order state transition service + order events. DONE
   - Add buyer order creation idempotency key. DONE
   - Fix external provider flow so wallet hold happens before provider reservation and failures refund holds. DONE

3. P0 stock/pricing correctness:
   - Fix nullable `operator` unique constraint risk by normalizing operator to a non-null key or adding partial unique indexes. DONE
   - Add price/stock freshness fields and a provider sync task. NOT DONE
   - Decide supplier inventory model (reservation callback vs exact inventory). DONE (reservation callback chosen + implemented; exact phone inventory not implemented)

4. P0 Redis/rate limit:
   - Replace in-memory `RateLimitMiddleware` with Redis-backed limiter. DONE
   - Use Redis counters for auth/login throttling and possibly order creation throttles. PARTIAL (global API rate limit uses Redis; per-endpoint throttles not implemented)

5. P0 SMS/order processing:
   - Add generic SMS/message table. DONE
   - Use `FOR UPDATE SKIP LOCKED` in polling task. DONE
   - Add internal webhook namespace and signature validation plan. PARTIAL (namespace exists with shared-secret auth; no provider-specific payload validation/processing yet)

6. P1 marketplace accounting:
   - Add supplier payout/withdrawal model. PARTIAL (request/hold/admin approve/reject/mark-paid skeleton; no external payout provider)
   - Add wallet transaction history endpoint for buyers.
   - Add supplier transaction/payout endpoints for suppliers. PARTIAL (payout request list/create exists; transaction list is admin-only)

7. P1 observability/admin:
   - Add pagination to admin/users/orders/supplier logs.
   - Add calculated stats for supplier/provider success rates.
   - Add audit logs for API key regeneration and supplier write actions.

What not to touch yet:

- Do not rewrite frontend layout before backend lifecycle/accounting is stable.
- Do not integrate real external providers until secret storage, provider sync, abuse controls, and provider reservation rollback are designed.
- Do not add many new catalog features before service/country/operator normalization is settled.
- Do not optimize provider routing deeply until real success-rate stats exist.

Risks to close before adding new features:

- Money must remain transactionally correct under concurrency.
- One order must never receive a number that another active order can also use.
- Buyer APIs must not expose provider cost or internal supplier economics.
- Rate limits must work across multiple backend processes.
- Supplier and payment callbacks must be authenticated and idempotent.
