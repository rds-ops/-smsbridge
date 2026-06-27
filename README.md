# smsbridge

smsbridge is a compliance-first SMS verification testing API marketplace MVP for developers, QA teams, wholesale clients and international onboarding checks. It uses a `MockProvider` first and intentionally avoids real provider integrations, automatic payment providers and number rental in the first version.

Illegal use, spam, phishing, fraud, abusive automation, fake identity usage and ban bypass workflows are prohibited by design and must not be added.

## Stack

- Backend: FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL
- Cache and jobs: Redis, Celery
- Frontend: Next.js, TypeScript, Tailwind CSS
- Tests: pytest
- Deployment: Docker Compose

## Local Setup

```bash
cp .env.example .env
docker compose up --build
```

Services:

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Swagger docs: http://localhost:8000/docs
- PostgreSQL: localhost:5432
- Redis: localhost:6379

Future recommended production-style deployment:

- `www.smsbridge.com` for marketing and legal pages
- `app.smsbridge.com` for the client dashboard
- `admin.smsbridge.com` for internal admin tools
- `api.smsbridge.com` for the backend API

The current MVP intentionally keeps admin inside the main frontend, but the code is organized so admin components and API helpers can be extracted later.

Frontend organization:

- `app/admin/*` keeps internal admin routes together.
- `components/admin/*` and `lib/admin/*` contain admin-only UI and API helpers.
- `components/client/*` and `lib/client/*` contain client dashboard/order helpers.
- `components/shared/*` and `lib/shared/*` contain reusable UI, API client, formatting and shared types.

## Default Accounts

- Admin: `admin@smsbridge.local` / `change-me`
- Test user: `user@smsbridge.local` / `change-me`

Change these before any real deployment.

## Local Test Flow

For the full local marketplace flow, including `manual_test` payment intents, fake supplier reservation, supplier SMS push, finishing an order, and release callback checks, see:

- `docs/LOCAL_E2E_TESTING.md`

Optional helper:

```bash
python tools/local_e2e_smoke.py
```

The helper uses only the Python standard library and is for local manual smoke testing, not CI.

Quick frontend smoke path:

1. Start the stack: `docker compose up --build`
2. Open the frontend: http://localhost:3000
3. Sign in as admin: `admin@smsbridge.local` / `change-me`
4. Open `/admin` and add funds or complete a local `manual_test` payment intent.
5. Log out, then sign in as user: `user@smsbridge.local` / `change-me`
6. Open `/buy`, choose a service and country, and buy a mock/supplier number.
7. If SMS arrives, finish the order to capture the hold. If you cancel before SMS, the hold is refunded.
8. Confirm balance and held balance on `/dashboard`, and check history on `/orders`.

## Backend Commands

From `apps/backend`:

```bash
python3 -m pip install -r requirements.txt
alembic upgrade head
python3 -m app.db.seed
python3 -m pytest app/tests
uvicorn app.main:app --reload
```

## Environment Variables

See `.env.example`.

Important values:

- `DATABASE_URL`
- `REDIS_URL`
- `SECRET_KEY`
- `CORS_ORIGINS`
- `MOCK_SUCCESS_RATE`
- `MOCK_SMS_DELAY_SECONDS`
- `MOCK_ORDER_TIMEOUT_SECONDS`
- `RATE_LIMIT_PER_MINUTE`
- `API_REQUEST_LOG_RETENTION_DAYS`
- `PAYMENT_WEBHOOK_EVENT_RETENTION_DAYS`
- `SUPPLIER_RELEASE_RETRY_RETENTION_DAYS`

Operational retention policy:

- `docs/RETENTION_POLICY.md`

## API Examples

Login:

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@smsbridge.local","password":"change-me"}'
```

Create order:

```bash
curl -X POST http://localhost:8000/api/v1/orders \
  -H "Authorization: Bearer $TOKEN_OR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"service_code":"telegram","country_iso2":"ID"}'
```

Manual admin deposit:

```bash
curl -X POST http://localhost:8000/admin/wallets/deposit \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id":2,"amount":"25.00","reference":"manual"}'
```

Client API key access uses the same `/api/v1` endpoints with `Authorization: Bearer <user_api_key>`. The dashboard only shows a generated API key once; regenerate it from the API docs page when needed.

Get balance:

```bash
curl http://localhost:8000/api/v1/balance \
  -H "Authorization: Bearer $USER_API_KEY"
```

Get prices:

```bash
curl "http://localhost:8000/api/v1/prices?service_code=telegram&country_iso2=ID" \
  -H "Authorization: Bearer $USER_API_KEY"
```

## Wallet and Order Lifecycle

The wallet has `balance` and `held_balance`. Buying a number creates an order and a wallet hold. The hold moves funds from balance into held balance. Finishing an order after SMS receipt captures the hold. Cancellation or expiration refunds the hold. Capture and refund are idempotent and every movement creates a wallet transaction.

Order flow:

1. User creates order for service/country/operator.
2. Provider router selects an active provider with available price.
3. `MockProvider` returns a test phone number.
4. Wallet hold is created.
5. Celery beat polls waiting orders every 5 seconds.
6. SMS receipt moves order to `sms_received`.
7. User finishes order to capture hold, or cancels before completion to refund.
8. Expired orders are automatically refunded.

## Supplier Module

smsbridge now has an aggregator foundation:

```text
Supplier -> smsbridge -> client
```

Suppliers do not have a frontend cabinet yet. Admin manages suppliers under `/admin`, generates supplier API keys, and can inspect supplier inventory, activations, pushed SMS and transactions. Supplier API keys are hashed in the database and are shown only once after regeneration.

Supplier data model highlights:

- `Supplier`: status, reward percent, balance, held balance and notes.
- `SupplierInventory`: availability by service, country and optional operator.
- `SupplierActivation`: supplier-side reservation linked to a client order.
- `SupplierSms`: idempotent pushed SMS records.
- `SupplierTransaction`: supplier rewards, payouts and manual adjustments.

Supplier reward is stored when an activation is created:

```text
supplier_reward = order.price * supplier.reward_percent / 100
```

Rewards are paid only when the client order is completed. Cancelled, expired or refunded orders do not create supplier reward transactions. Reward creation is idempotent, so the same order cannot pay the supplier twice.

## Supplier API

Supplier endpoints live under `/supplier/v1` and require a Bearer supplier API key.

Check supplier account:

```bash
curl http://localhost:8000/supplier/v1/me \
  -H "Authorization: Bearer $SUPPLIER_API_KEY"
```

Update inventory:

```bash
curl -X POST http://localhost:8000/supplier/v1/inventory/update \
  -H "Authorization: Bearer $SUPPLIER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {
        "service_code": "telegram",
        "country_iso2": "ID",
        "operator": "any",
        "available_count": 25,
        "success_rate": 88.5,
        "avg_sms_time_seconds": 45,
        "status": "active"
      }
    ]
  }'
```

Push SMS:

```bash
curl -X POST http://localhost:8000/supplier/v1/sms \
  -H "Authorization: Bearer $SUPPLIER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "supplier_sms_id": "sms_123",
    "phone_number": "+62878822167",
    "phone_from": "Telegram",
    "text": "Telegram code: 123456",
    "supplier_activation_id": "sup_act_123"
  }'
```

Duplicate `supplier_sms_id` values return success with `duplicate: true`, so suppliers can safely retry webhook delivery.

Create a payout request:

```bash
curl -X POST http://localhost:8000/supplier/v1/payout-requests \
  -H "Authorization: Bearer $SUPPLIER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": "25.0000",
    "payout_method": "manual_test",
    "payout_address": "local-test-address"
  }'
```

Supplier payout requests are an accounting skeleton. Creating a request requires an active supplier, sufficient balance, `payout_method`, `payout_address`, and at least `SUPPLIER_PAYOUT_MIN_AMOUNT` (default `1.0000`). Creating a request moves supplier funds from `balance` to `held_balance` and writes a supplier ledger transaction. Admin can approve, reject, or mark paid, but no external payout provider is integrated yet.

## Supplier Pool Provider

`supplier_pool` is a provider type that lets the existing order router use active supplier inventory. In development mode it safely simulates number issuing from supplier inventory:

- active supplier inventory becomes visible in `/api/v1/prices`
- buying a matching number decrements available inventory
- a `SupplierActivation` is created and linked to the client `Order`
- SMS can be pushed through `/supplier/v1/sms`
- finishing the order captures the client hold and creates the supplier reward

`MockProvider` remains available as the development fallback when no supplier inventory matches.

For local supplier callback testing, run the dev-only fake supplier server:

```bash
docker compose --profile dev up -d fake-supplier
```

Use `http://fake-supplier:8010/v1/reservations` as the supplier reservation URL when the backend is running in Docker Compose.

## Wholesale Client Foundation

User tiers and default limits:

| Tier | Orders/min | Orders/day | Active orders | Daily spend |
| --- | ---: | ---: | ---: | ---: |
| default | 3 | 20 | 3 | 10 USD |
| verified | 10 | 200 | 20 | 100 USD |
| wholesale | 60 | 5000 | 500 | 5000 USD |
| partner | 300 | 50000 | 5000 | 50000 USD |

Admins manually upgrade users and can still override individual limits. There is no automatic wholesale approval.

## Provider Adapters

Provider code lives under `apps/backend/app/providers`.

- `BaseProvider` defines the adapter contract.
- `MockProvider` supports MVP testing.
- `SupplierPoolProvider` uses active supplier inventory through the supplier module.
- `FiveSimProvider`, `SmsActivateProvider` and `SmsManProvider` are clean placeholders with TODOs.

Real provider work should stay inside adapters and must include compliance review, secret handling and tests.

## Compliance Placeholders

Static pages exist for:

- `/acceptable-use`
- `/terms`
- `/privacy`
- `/abuse`

They currently contain placeholder text and must be replaced by reviewed legal text before production.

## Next Development Steps

- Add proper admin user creation and password rotation.
- Add provider settings UI and encrypted secret storage.
- Expand API key management with last-used timestamps and key names.
- Add production-grade distributed rate limiting.
- Add provider webhooks only after abuse controls are mature.
- Keep RU/EN localization coverage complete as new screens are added.
- Add CI for backend tests and frontend build.

## Developer Commands And Next Steps

Local Docker commands:

```bash
docker compose up --build
docker compose up
docker compose down
docker compose down --volumes
docker compose logs backend
docker compose logs frontend
docker compose logs worker
docker compose exec backend alembic upgrade head
docker compose exec backend python -m pytest
```

Smoke test commands:

```bash
curl http://localhost:8000/health
open http://localhost:3000
open http://localhost:8000/docs
```

Manual MVP test checklist:

1. Start Docker
2. Login as admin
3. Deposit funds to user
4. Login as user
5. Buy mock number
6. Wait for SMS
7. Finish order
8. Check balance
9. Test cancel/refund
10. Check admin metrics

Supplier flow test:

1. Login as admin
2. Create supplier
3. Activate supplier
4. Regenerate supplier API key
5. Use supplier API key to update inventory
6. Login as user
7. Deposit balance manually
8. Buy number
9. Push SMS through supplier API
10. Check order becomes `sms_received`
11. Finish order
12. Check supplier reward transaction
13. Check platform gross profit

Roadmap:

- Stage 1: stabilize MVP, improve UI, test full mock flow
- Stage 2: add real supplier/provider integration, provider health checks, provider request logs, provider fallback
- Stage 3: improve pricing engine, add per-country/service markup, add wholesale tiers, add better admin finance reports
- Stage 4: improve client API, add 5sim/SMS-Activate compatible API mode if possible, add API docs for resellers
- Stage 5: split admin into a separate app later across `www.smsbridge.com`, `app.smsbridge.com`, `admin.smsbridge.com`, and `api.smsbridge.com`

## Troubleshooting

### Frontend Shows `Invalid token`

This usually means the browser has an old `access_token` from a previous Docker run or from a different `SECRET_KEY`.

Fix:

1. Use the Logout button, or clear site storage for `localhost:3000`.
2. Sign in again with the seed account.
3. For admin actions, make sure the current account is `admin@smsbridge.local`.

The frontend API client clears stale tokens after a 401 and redirects back to login. Admin-only API calls return 403 for normal users.

### Worker Is Not Polling Orders

Check the worker logs:

```bash
docker compose logs worker
```

Expected startup output includes:

```text
Registered tasks: ['app.jobs.tasks.poll_waiting_orders']
```

Expected runtime output includes successful executions of `app.jobs.tasks.poll_waiting_orders`.
