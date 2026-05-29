# Architecture Map

## 1. System Overview

`smsbridge` is an early MVP of a 5sim-like SMS number marketplace. Buyers buy temporary phone numbers for a service/country/operator combination. Suppliers or external providers supply numbers and SMS messages. Admins manage users, providers, suppliers, balances, limits, and operational visibility.

Main roles:

- `buyer`: registered user or API-key client that views prices, buys numbers, checks orders, cancels orders, and finishes orders after SMS is received.
- `supplier`: marketplace partner that sends inventory/count updates and pushes SMS messages through `/supplier/v1`.
- `admin`: internal operator that manages users, wallets, providers, suppliers, refunds, limits, metrics, and audit logs.
- `external provider`: third-party SMS activation provider such as 5sim, SMS-Activate, Sms-man, or the current mock provider.
- `internal worker`: Celery process that polls waiting orders and handles background work.

## 2. Main Components

### Next.js frontend

- Location: `apps/frontend`
- Uses Next.js App Router.
- Main user pages: dashboard, buy, orders, order detail, settings, login, register.
- Main admin page: `apps/frontend/app/admin/page.tsx`
- API clients:
  - `apps/frontend/lib/client/api.ts` for buyer API.
  - `apps/frontend/lib/admin/api.ts` for admin API.
  - `apps/frontend/lib/shared/api.ts` for shared fetch/auth token handling.

### FastAPI backend

- Location: `apps/backend/app`
- Entrypoint: `app/main.py`
- Routers:
  - `app/api/auth.py`
  - `app/api/api_v1.py`
  - `app/api/supplier.py`
  - `app/api/admin.py`
- Services:
  - `app/services/orders.py`
  - `app/services/wallet.py`
  - `app/services/suppliers.py`
  - `app/services/limits.py`
  - `app/services/audit.py`
- Current separation is acceptable for MVP, but routers still contain direct ORM queries, especially admin/list endpoints.

### PostgreSQL

- Stores all durable business state.
- SQLAlchemy models are in `apps/backend/app/models/entities.py`.
- Alembic migrations are in `apps/backend/alembic/versions`.
- Critical durable state must stay here: users, wallets, orders, transactions, suppliers, inventory, SMS, audit logs.

### Redis

- Configured by `settings.redis_url`.
- Currently used as Celery broker and result backend.
- Not currently used for distributed rate limiting, locks, idempotency, or durable business state.

### Celery worker

- Location:
  - `apps/backend/app/jobs/celery_app.py`
  - `apps/backend/app/jobs/tasks.py`
- Current task: `poll_waiting_orders`.
- It polls `orders` with `status = waiting_sms` and asks external provider adapters for status.

### Adminer

- Defined in `docker-compose.yml`.
- Exposes database UI on port `8080`.
- Useful for local development only. It should be protected or disabled in production.

### External provider adapters

- Location: `apps/backend/app/providers`
- Current adapters:
  - `mock.py` works as local fake provider.
  - `supplier_pool.py` is a DB-backed supplier pool marker.
  - `five_sim.py`, `sms_activate.py`, `sms_man.py` are placeholders.
- Adapter selection is in `providers/router.py`.

### Supplier API

- Router: `apps/backend/app/api/supplier.py`
- Prefix: `/supplier/v1`
- Uses supplier API key auth from `core/deps.py`.
- Current functions:
  - supplier profile
  - inventory update
  - inventory list
  - SMS push

## 3. Request Flow: Buyer Buys Number

Current endpoint:

- `POST /api/v1/orders`
- Router: `apps/backend/app/api/api_v1.py`
- Service: `apps/backend/app/services/orders.py::create_order`

Current flow:

1. Buyer calls `POST /api/v1/orders` with `service_code`, `country_iso2`, optional `operator`.
2. Backend validates service and country through `services/suppliers.py::validate_service_country`.
3. Backend finds candidate prices through `providers/router.py::candidate_prices`.
4. Candidates are ordered by provider priority and final customer price.
5. For each candidate, backend enforces buyer limits with `services/limits.py::enforce_can_order`.
6. If provider type is `supplier_pool`:
   - Backend creates an `Order` with `status = waiting_sms`.
   - Backend selects supplier inventory with `SELECT ... FOR UPDATE`.
   - Backend decrements `supplier_inventory.available_count`.
   - Backend creates `SupplierActivation`.
   - Backend generates a fake supplier phone number.
   - Backend creates wallet hold.
   - Router commits and returns order/phone.
7. If provider is external/mock:
   - Backend calls adapter `get_number`.
   - Adapter returns `provider_order_id` and `phone_number`.
   - Backend creates `Order`.
   - Backend creates wallet hold.
   - Router commits and returns order/phone.

How it is implemented now:

- Order creation and wallet hold are in service code.
- Supplier pool reservation uses DB row locking on `SupplierInventory`.
- Wallet hold locks wallet row and creates `WalletTransaction(type='hold')`.
- Router commits after service returns.

Risk:

- External provider reservation happens before wallet hold. If wallet hold fails, the provider number may already be reserved and not cancelled.
- Buyer order creation has no idempotency key. A retry can create multiple orders.
- Supplier pool uses generated fake phone numbers, not real supplier numbers.
- External provider local `prices.available_count` is not decremented after purchase.
- State transitions are direct string assignments, not an explicit state machine.

Correct target flow:

1. Validate buyer, service, country, operator, limits, and idempotency key.
2. Start explicit transaction.
3. Lock wallet or pre-authorize hold before irreversible provider reservation.
4. Select provider/stock.
5. Reserve number with rollback/cancel handling.
6. Create order and activation/provider mapping.
7. Create wallet hold transaction.
8. Commit.
9. Return stable order response.

For external providers, if provider reservation must happen before wallet mutation, the code needs a guaranteed compensation path: cancel provider order if DB commit or wallet hold fails.

## 4. Request Flow: SMS Received

### Scenario A: external provider through polling

Current worker:

- Task: `app.jobs.tasks.poll_waiting_orders`
- Runs through Celery beat every 5 seconds.

Current flow:

1. Worker selects up to 100 orders where `orders.status = waiting_sms`.
2. For each order, `services/orders.py::poll_order` is called.
3. If order is expired:
   - `wallet.refund` is called.
   - `orders.status` becomes `expired`.
   - supplier activation is marked expired if present.
4. If provider is `supplier_pool`, polling returns without external status check.
5. For external provider:
   - Adapter `get_order_status(provider_order_id)` is called.
   - If provider returns SMS:
     - `orders.status` becomes `sms_received`.
     - `orders.sms_code` is set.
     - `orders.sms_text` is set.
   - If provider returns timeout/failed:
     - wallet hold is refunded.
     - order status becomes `expired` or `failed`.

Tables/fields updated:

- `orders.status`
- `orders.sms_code`
- `orders.sms_text`
- `wallets.balance`
- `wallets.held_balance`
- `wallet_transactions`
- possibly `supplier_activations.status` if the order uses supplier pool

Risk:

- External provider SMS is not stored in a generic SMS/message table.
- Polling query does not use `FOR UPDATE SKIP LOCKED`; multiple workers could process the same order.
- There is no internal webhook namespace for providers that support callbacks.

### Scenario B: supplier through `POST /supplier/v1/sms`

Current endpoint:

- `POST /supplier/v1/sms`
- Router: `apps/backend/app/api/supplier.py`
- Service: `services/suppliers.py::push_sms`

Current flow:

1. Supplier authenticates with supplier API key.
2. Supplier sends:
   - `supplier_sms_id`
   - `phone_number`
   - optional `phone_from`
   - `text`
   - optional `supplier_activation_id`
3. Backend checks duplicate by `(supplier_id, supplier_sms_id)`.
4. Backend finds activation by `supplier_activation_id` if provided.
5. If not provided, backend finds latest active activation by supplier and phone number.
6. Backend extracts SMS code with regex.
7. Backend creates `SupplierSms`.
8. Backend updates `SupplierActivation`:
   - `status = sms_received`
   - `sms_text`
   - `sms_code`
9. Backend updates `Order` if it is not terminal:
   - `status = sms_received`
   - `sms_text`
   - `sms_code`

Tables/fields updated:

- `supplier_sms`
- `supplier_activations.status`
- `supplier_activations.sms_text`
- `supplier_activations.sms_code`
- `orders.status`
- `orders.sms_text`
- `orders.sms_code`

Risk:

- Phone-number fallback can attach SMS to the latest active activation if activation id is missing.
- Supplier SMS endpoint is not currently included in request logging middleware.
- No generic `sms_messages` table for one consistent message model.

## 5. Request Flow: Cancel / Finish / Expire Order

Current order statuses:

- `created`
- `waiting_sms`
- `sms_received`
- `completed`
- `cancelled`
- `expired`
- `failed`
- `refunded`

Current lifecycle:

```text
created
  -> waiting_sms
  -> sms_received
  -> completed

waiting_sms
  -> cancelled
  -> expired
  -> failed

sms_received
  -> completed
  -> cancelled currently allowed by cancel_order unless blocked by status logic

waiting_sms/sms_received
  -> refunded by admin path depending on wallet state
```

Cancel flow:

- Endpoint: `POST /api/v1/orders/{public_id}/cancel`
- Service: `orders.cancel_order`
- If status is `cancelled`, `expired`, or `refunded`, returns as idempotent success.
- If status is `completed` or `failed`, returns conflict.
- For external provider order, calls adapter `cancel_order`.
- Calls `wallet.refund`.
- Sets `orders.status = cancelled`.
- Marks supplier activation `cancelled` if present.

Finish flow:

- Endpoint: `POST /api/v1/orders/{public_id}/finish`
- Service: `orders.finish_order`
- If status is `completed`, returns as idempotent success.
- Only allowed when `status = sms_received`.
- For external provider order, calls adapter `finish_order`.
- Calls `wallet.capture`.
- Sets `orders.status = completed`.
- Credits supplier reward if supplier activation exists.

Expire flow:

- Worker calls `orders.poll_order`.
- If `expires_at <= now` and order is `waiting_sms`:
  - Calls `wallet.refund`.
  - Sets `orders.status = expired`.
  - Marks supplier activation `expired`.

Where explicit state machine is needed:

- Statuses are plain strings.
- Valid transitions are spread across `orders.py` and `suppliers.py`.
- There is no single transition function that says which status can move to which next status.
- There is no `order_events` history.

Recommended target:

- Add `services/order_state.py`.
- Define allowed transitions in one place.
- Record every transition in `order_events`.
- Add timestamps such as `sms_received_at`, `completed_at`, `cancelled_at`, `expired_at`, `refunded_at`.

## 6. Money Flow

### Wallet balance

`wallets.balance` is the buyer's available money.

Implemented:

- Admin deposit increases balance.
- Admin adjustment changes balance and prevents negative balance.
- Order hold decreases balance.
- Refund increases balance.

Missing:

- Real payment/deposit provider flow.
- Buyer wallet transaction history endpoint.
- DB check constraint for non-negative balance.

### Held balance

`wallets.held_balance` is money reserved for active orders.

Implemented:

- `hold` moves money from `balance` to `held_balance`.
- `capture` decreases `held_balance`.
- `refund` decreases `held_balance` and returns money to `balance`.

Missing:

- DB check constraint for non-negative held balance.
- Reconciliation job that verifies wallet balances against ledger.

### Hold

Implemented in `services/wallet.py::hold`.

- Checks amount is positive.
- Checks enough available balance.
- Locks wallet row.
- Creates `WalletTransaction(type='hold')`.
- Idempotent per order because of transaction lookup and unique constraint.

### Capture

Implemented in `services/wallet.py::capture`.

- Used when buyer finishes an order after SMS received.
- Decreases held balance.
- Creates `WalletTransaction(type='capture')`.
- Idempotent if capture already exists.
- Refuses capture if refund already exists.

### Refund

Implemented in `services/wallet.py::refund`.

- Used on cancel/expire/refund paths.
- Moves held balance back to balance.
- Creates `WalletTransaction(type='refund')`.
- Idempotent if refund already exists.
- Refuses refund if capture already exists.

### Supplier reward

Implemented in `services/suppliers.py::complete_supplier_reward`.

- Called when buyer finishes supplier-pool order.
- Credits `suppliers.balance`.
- Creates `SupplierTransaction(type='reward')`.
- Idempotent by `(supplier_id, order_id, type, status)`.

### Admin deposit

Implemented:

- Endpoint: `POST /admin/wallets/deposit`
- Service: `wallet.deposit`
- Creates `WalletTransaction(type='deposit')`.

Risk:

- Manual deposits are not idempotent.
- No real payment intent/provider reference.

### Supplier payout

Not found in current codebase.

Needed:

- `supplier_payouts` or `withdrawal_requests` table.
- Supplier endpoint to request payout.
- Admin approve/reject/mark-paid endpoints.
- Use `suppliers.held_balance` for pending withdrawals.
- Ledger transactions for payout hold, payout completion, payout cancellation.

## 7. Pricing Flow

Current storage:

- `prices.provider_cost`: internal cost from provider or supplier pool.
- `prices.final_price`: customer-facing price.
- `orders.price`: frozen customer price at purchase time.
- `orders.provider_cost`: frozen provider/supplier cost at purchase time.
- `providers.default_markup_percent`: default markup for seeded/mock provider pricing.

Current markup logic:

- `providers/router.py::final_price(provider_cost, markup_percent)` calculates:

```text
final_price = provider_cost * (1 + markup_percent / 100)
```

Supplier pool logic:

- `sync_supplier_pool_price` uses cheapest active non-supplier-pool `final_price` as reference.
- Supplier pool provider cost is set to 70% of that final price.
- Supplier reward is calculated as `order.price * supplier.reward_percent / 100`.

Why buyer must not see `provider_cost`:

- `provider_cost` reveals marketplace margin.
- It exposes supplier/provider economics.
- It makes price negotiation and abuse easier.
- It is internal accounting data, not buyer product data.

Current issue:

- Buyer schema `PriceOut` includes `provider_cost`.
- `/api/v1/prices` returns that schema.

Correct pricing architecture:

- Public/buyer price response:
  - service
  - country
  - operator
  - final customer price
  - approximate or exact available count
  - delivery rate if safe to expose
- Admin/internal price response:
  - provider
  - provider cost
  - final price
  - markup
  - margin
  - freshness
- Pricing policy tables:
  - global markup
  - provider-specific markup
  - service/country/operator override
  - minimum price
  - rounding rules
- Provider price sync:
  - fetch provider cost/stock
  - apply pricing policy
  - store final price
  - track freshness and sync errors

## 8. Stock / Count Flow

Current `available_count` behavior:

- External/mock provider stock is stored in `prices.available_count`.
- Supplier stock is stored in `supplier_inventory.available_count`.
- Supplier pool aggregate stock is stored in a synthetic `prices` row for provider `supplier_pool`.
- Supplier pool aggregate count is calculated as the sum of active supplier inventory rows.

External provider stock:

- Source: provider adapter or seed/mock data.
- Current mock data creates fixed counts.
- On purchase, local `prices.available_count` is not decremented.
- For real providers, this should be treated as cached/advisory unless synced often.

Supplier inventory:

- Source: supplier calls `POST /supplier/v1/inventory/update`.
- Supplier sends count by service/country/operator.
- On reservation, backend selects one `supplier_inventory` row and decrements count.

Why count-only supplier inventory is risky:

- Backend does not know the real phone numbers in advance.
- Supplier can report count but fail to provide a real number.
- Backend currently generates fake phone numbers for supplier pool.
- Count-only does not prevent supplier from reusing the same real number elsewhere.
- It makes duplicate-number prevention difficult.

Decision needed:

Option 1: exact phone inventory.

- Supplier uploads individual phone numbers.
- Backend reserves one exact number with row locking.
- Stronger duplicate prevention.
- More DB rows and privacy/security concerns.

Option 2: reservation callback.

- Supplier reports count only.
- When buyer purchases, backend asks supplier to reserve a number.
- Supplier returns real phone number and supplier activation id.
- Requires supplier callback/API availability and timeout handling.

For this project, one of these strategies must be chosen before supplier pool can be production-grade.

## 9. Database Map

| Table | Purpose | Connected to | Critical Notes |
|---|---|---|---|
| `users` | Buyer/admin accounts | `wallets`, `user_limits`, `orders`, `wallet_transactions`, `audit_logs`, `api_request_logs` | Role/status are strings. No session/revoked-token table. |
| `wallets` | Buyer balance and held balance | `users`, `wallet_transactions` | Service prevents negative balances, but DB constraints are missing. |
| `wallet_transactions` | Buyer wallet ledger | `users`, `orders` | Hold/capture/refund are idempotent per order/type/status. Deposit/adjustment idempotency is missing. |
| `providers` | External provider or supplier-pool config | `prices`, `orders` | Real API key encryption not implemented. Placeholder adapters exist. |
| `services` | Product/service catalog | Referenced by code from `prices`, `orders`, `supplier_inventory` | No FK from code fields. |
| `countries` | Country catalog | Referenced by code from `prices`, `orders`, `supplier_inventory` | No FK from code fields. |
| `prices` | Provider price/stock by service/country/operator | `providers`, used by order creation | Buyer API currently exposes provider cost. Nullable operator unique constraint is risky in PostgreSQL. |
| `orders` | Buyer number purchase lifecycle | `users`, `providers`, `wallet_transactions`, `supplier_activations`, `supplier_sms`, `supplier_transactions` | Needs explicit state machine and event history. |
| `suppliers` | Supplier accounts and balances | `supplier_inventory`, `supplier_activations`, `supplier_sms`, `supplier_transactions` | No payout model yet. |
| `supplier_inventory` | Supplier count by service/country/operator | `suppliers`, synthetic supplier-pool `prices` | Count-only inventory is not enough for real phone reservation unless reservation callback exists. |
| `supplier_activations` | Supplier-side reservation mapped to buyer order | `suppliers`, `orders`, `supplier_sms`, `supplier_transactions` | Current supplier phone is fake-generated. |
| `supplier_sms` | SMS messages pushed by suppliers | `suppliers`, `supplier_activations`, `orders` | Idempotent by supplier SMS id. No generic SMS table for all providers. |
| `supplier_transactions` | Supplier ledger | `suppliers`, `supplier_activations`, `orders` | Reward implemented. Payout/withdrawal missing. |
| `audit_logs` | Admin/system audit trail | `users` actor | No supplier actor support. More events should be audited. |
| `api_request_logs` | API request log | `users` | Supplier endpoints not logged currently. No duration/user-agent. |

## 10. API Map

| Namespace | Main endpoints | Role | Purpose | Notes |
|---|---|---|---|---|
| `auth` | `/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/me` | public/authenticated user | User registration, login, token refresh, current user | No token revocation/session table. |
| `public` | Not found in current codebase | public | Public catalog/prices/health | Should be added for service/country/price discovery. |
| `api/v1 buyer` | `/api/v1/balance`, `/api/v1/services`, `/api/v1/countries`, `/api/v1/prices`, `/api/v1/orders`, `/api/v1/orders/{public_id}`, `/cancel`, `/finish`, `/api-key/regenerate`, `/limits` | buyer/API key depending on endpoint | Buyer API for prices, orders, wallet balance, limits | Auth mode is inconsistent. `prices` leaks `provider_cost`. |
| `supplier/v1` | `/supplier/v1/me`, `/supplier/v1/inventory`, `/supplier/v1/inventory/update`, `/supplier/v1/sms` | supplier | Supplier profile, stock updates, SMS push | No supplier payouts or activation list for supplier. |
| `admin` | `/admin/users`, `/admin/orders`, `/admin/providers`, `/admin/suppliers`, `/admin/wallets/*`, `/admin/audit-logs`, `/admin/api-request-logs`, `/admin/metrics` | admin | Back-office operations | Admin APIs mostly direct ORM. Pagination limited. |
| `internal` | Not found in current codebase | internal worker/provider/payment callbacks | Webhooks, reconciliation, internal jobs | Needed for provider callbacks, payment webhooks, signed internal operations. |

## 11. Risk Map

| Risk | Priority | Why dangerous | Where in code | Fix direction |
|---|---|---|---|---|
| Buyer API exposes `provider_cost` | P0 | Leaks margin and supplier/provider economics | `schemas/common.py::PriceOut`, `/api/v1/prices` | Split buyer/admin price schemas; remove cost from buyer response. |
| External provider reservation before wallet hold | P0 | Can reserve provider number without successful payment hold | `services/orders.py::create_order` | Lock/pre-hold wallet first or add compensation cancel path and explicit transaction. |
| No order creation idempotency | P0 | API retry can buy multiple numbers | `/api/v1/orders`, `services/orders.py` | Add idempotency key table and request handling. |
| Supplier pool fake phone numbers | P0 | Marketplace supplier flow is not real production inventory | `services/suppliers.py::_fake_supplier_phone` | Choose exact phone inventory or supplier reservation callback. |
| In-memory rate limiting | P0 | Breaks with multiple backend workers and restarts | `core/middleware.py::RateLimitMiddleware` | Move rate limits to Redis. |
| No DB money constraints | P0 | Service bug could create negative balances | `models/entities.py`, migrations | Add DB check constraints for wallet/supplier balances. |
| No explicit order state machine | P0 | Invalid transitions become easy as system grows | `services/orders.py`, `services/suppliers.py` | Centralize transition rules and add order events. |
| No generic SMS message table | P0 | External provider SMS is not persistently modeled like supplier SMS | `orders.sms_text`, `orders.sms_code`, `supplier_sms` | Add `sms_messages` or `order_messages`. |
| Nullable operator unique constraints | P0 | PostgreSQL can allow duplicate rows where operator is NULL | `prices`, `supplier_inventory` | Use non-null operator key or partial unique indexes. |
| Default admin credentials and default secret | P0 | Production takeover risk | `db/seed.py`, `core/config.py`, `.env.example`, `docker-compose.yml` | Fail startup in production unless secure values are set. |
| Supplier endpoints not request-logged | P1 | Reduced auditability for supplier writes | `core/middleware.py` | Include `/supplier` and supplier actor id in logs. |
| No payment/deposit model | P1 | Manual deposits cannot support real users safely | `admin.wallets/deposit` only | Add payment intents, provider refs, webhooks, idempotency. |
| No supplier payout lifecycle | P1 | Suppliers cannot withdraw through system | Not found in current codebase | Add payout requests, holds, admin approval, ledger events. |
| Provider adapters mostly placeholders | P1 | Real stock/order lifecycle not implemented | `providers/five_sim.py`, `sms_activate.py`, `sms_man.py` | Implement after secrets, abuse controls, sync jobs. |
| No stats/rate calculation | P1 | Provider/supplier routing cannot optimize quality | Only self-reported `success_rate` | Add stats aggregation from actual orders/activations. |
| Admin lists lack pagination | P2 | Admin pages will degrade as data grows | `api/admin.py` list endpoints | Add cursor or limit/offset pagination. |
| Public catalog missing | P2 | Users cannot browse without auth | Not found in current codebase | Add `/public/services`, `/public/countries`, `/public/prices`. |

## 12. Build Plan

### Phase 1: Stabilize Core P0

- Remove `provider_cost` from buyer API.
- Add explicit order state machine.
- Fix order creation, wallet hold, and provider reservation ordering.
- Add buyer order creation idempotency.
- Replace in-memory rate limiting with Redis rate limiting.
- Add DB constraints for non-negative wallet and supplier balances.
- Add generic SMS messages table.
- Decide supplier real number strategy:
  - exact phone inventory, or
  - supplier reservation callback.
- Fix nullable `operator` uniqueness risk in `prices` and `supplier_inventory`.
- Add production guard for default secret and default admin password.

### Phase 2: Marketplace Accounting P1

- Add real payment/deposit flow:
  - payment intent table
  - payment provider references
  - signed internal payment webhook
  - idempotent deposit crediting
- Add supplier payout flow:
  - payout request
  - supplier balance hold
  - admin approval/rejection
  - mark paid
  - supplier transaction ledger entries
- Add supplier/provider stats:
  - success rate
  - SMS received rate
  - completion rate
  - average SMS time
  - service/country/operator/provider breakdown
- Add buyer wallet transaction endpoint.
- Add API key management:
  - multiple keys
  - labels
  - scopes
  - last used time
  - safe rotation.

### Phase 3: Polish P2

- Add public catalog endpoints.
- Improve API docs and examples.
- Add pagination/filtering to admin and buyer list endpoints.
- Improve frontend workflows after backend lifecycle and accounting are stable.
- Add better operational dashboards and reconciliation views.

## 13. Glossary

`buyer`

A user who buys a temporary phone number and waits for SMS. In current code this is a `User` with role `user`.

`supplier`

A marketplace partner that provides number stock and SMS messages through `/supplier/v1`. In current code this is a separate `Supplier` model authenticated by supplier API key.

`provider`

An external SMS activation source or internal supplier pool. Current provider rows live in `providers`. Examples: `mock`, `supplier_pool`, future `5sim`, `sms_activate`, `sms_man`.

`order`

Buyer purchase of one phone number for one service/country/operator. Stored in `orders`.

`activation`

Supplier-side reservation connected to an order. Stored in `supplier_activations`. It maps supplier work to buyer order.

`wallet hold`

Temporary reservation of buyer money. It moves amount from `wallets.balance` to `wallets.held_balance` and creates `WalletTransaction(type='hold')`.

`capture`

Final charge of held money after successful order completion. It decreases `held_balance` and creates `WalletTransaction(type='capture')`.

`refund`

Return held money to available balance when order is cancelled, expired, or refunded before capture. It creates `WalletTransaction(type='refund')`.

`provider_cost`

Internal cost paid to provider or supplier. This is margin-sensitive and must not be shown to buyers.

`final_price`

Customer-facing price charged to buyer. Stored on `prices.final_price` and frozen on `orders.price`.

`available_count`

Number of available activations for a service/country/operator. For external providers it is cached provider stock. For suppliers it is count reported in `supplier_inventory`.

`delivery_rate`

Expected or measured chance of receiving SMS successfully. Current code stores it on `prices.delivery_rate`; supplier pool uses average supplier-reported success rates.

`state machine`

Central rule set that defines allowed order status transitions, such as `waiting_sms -> sms_received -> completed` or `waiting_sms -> cancelled`.

`idempotency`

Property that repeating the same request does not duplicate side effects. Wallet capture/refund are partly idempotent now. Order creation and deposits still need idempotency.

`webhook`

Server-to-server callback from provider/payment system to this backend. Current code does not have `/internal` webhooks yet; supplier SMS push is similar but belongs to supplier API.
