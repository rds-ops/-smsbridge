# Local E2E Testing Guide

Draft/internal. This guide is for local/dev testing only. It intentionally uses the `manual_test` payment provider and the local fake supplier server. Real payment providers such as Cryptomus/Payssion and real external SMS providers are deferred.

## 1. Start Local Services

From the repository root:

```bash
docker compose up -d postgres redis backend worker frontend
docker compose --profile dev up -d fake-supplier
```

The backend container runs migrations and seed on startup. To run them explicitly:

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.db.seed
```

Useful local URLs:

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:3000`
- Fake supplier from host: `http://localhost:8010`
- Fake supplier from backend container: `http://fake-supplier:8010`

Set shell variables for the curl examples:

```bash
BASE_URL=http://localhost:8000
FAKE_SUPPLIER_URL=http://localhost:8010
```

## 2. Health Checks

```bash
curl -sS "$BASE_URL/health/live"
curl -sS "$BASE_URL/health/ready"
```

Expected:

```json
{"status":"ok"}
```

and readiness should return `ready` when DB/Redis are reachable.

## 3. Login as Seeded Admin and Buyer

Seeded local credentials:

- Admin: `admin@smsbridge.local` / `change-me`
- Buyer: `user@smsbridge.local` / `change-me`

```bash
ADMIN_TOKEN=$(curl -sS -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@smsbridge.local","password":"change-me"}' | jq -r .access_token)

BUYER_TOKEN=$(curl -sS -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"user@smsbridge.local","password":"change-me"}' | jq -r .access_token)
```

## 4. Configure a Reservation-Enabled Supplier

Create an active supplier. The reservation URL must be reachable from the backend container, so use `http://fake-supplier:8010/v1/reservations`.

```bash
SUPPLIER_ID=$(curl -sS -X POST "$BASE_URL/admin/suppliers" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name":"Local Fake Supplier",
    "email":"fake-supplier@example.test",
    "status":"active",
    "reward_percent":"70.00",
    "reservation_enabled":true,
    "reservation_url":"http://fake-supplier:8010/v1/reservations",
    "reservation_auth_type":"none",
    "reservation_timeout_seconds":5
  }' | jq -r .id)
```

Generate a supplier API key:

```bash
SUPPLIER_API_KEY=$(curl -sS -X POST "$BASE_URL/admin/suppliers/$SUPPLIER_ID/api-key/regenerate" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq -r .api_key)
```

Add inventory:

```bash
curl -sS -X POST "$BASE_URL/supplier/v1/inventory/update" \
  -H "Authorization: Bearer $SUPPLIER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"items":[{"service_code":"telegram","country_iso2":"ID","operator":null,"available_count":10,"success_rate":"95.00","avg_sms_time_seconds":20,"status":"active"}]}'
```

This creates/updates supplier inventory and syncs the supplier pool price.

## 5. Create and Complete a manual_test Payment Intent

Create a buyer payment intent:

```bash
PAYMENT_PUBLIC_ID=$(curl -sS -X POST "$BASE_URL/api/v1/payment-intents" \
  -H "Authorization: Bearer $BUYER_TOKEN" \
  -H "Idempotency-Key: local-payment-1" \
  -H "Content-Type: application/json" \
  -d '{"amount":"10.0000","provider":"manual_test","currency":"USD"}' | jq -r .public_id)
```

Find its admin numeric id:

```bash
PAYMENT_ID=$(curl -sS "$BASE_URL/admin/payment-intents?provider=manual_test&limit=100" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  | jq -r --arg public_id "$PAYMENT_PUBLIC_ID" '.[] | select(.public_id == $public_id) | .id')
```

Complete it through the admin-only local/dev endpoint:

```bash
curl -sS -X POST "$BASE_URL/admin/payment-intents/$PAYMENT_ID/manual-complete" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

Verify wallet balance and transaction history:

```bash
curl -sS "$BASE_URL/api/v1/balance" \
  -H "Authorization: Bearer $BUYER_TOKEN"

curl -sS "$BASE_URL/api/v1/wallet/transactions?limit=10" \
  -H "Authorization: Bearer $BUYER_TOKEN"
```

Expected:

- Balance increases by the payment intent amount.
- Transaction history contains a `deposit` row with `reference = payment_intent:<public_id>`.

## 6. Create an Order Through Supplier Reservation

```bash
ORDER=$(curl -sS -X POST "$BASE_URL/api/v1/orders" \
  -H "Authorization: Bearer $BUYER_TOKEN" \
  -H "Idempotency-Key: local-order-1" \
  -H "Content-Type: application/json" \
  -d '{"service_code":"telegram","country_iso2":"ID","operator":null}')

ORDER_PUBLIC_ID=$(echo "$ORDER" | jq -r .public_id)
PHONE_NUMBER=$(echo "$ORDER" | jq -r .phone_number)
```

Expected:

- `status` is `waiting_sms`.
- `phone_number` starts with `+`.
- The supplier activation is stored internally; buyer responses do not expose the supplier activation id.

Inspect the order:

```bash
curl -sS "$BASE_URL/api/v1/orders/$ORDER_PUBLIC_ID" \
  -H "Authorization: Bearer $BUYER_TOKEN"
```

## 7. Push SMS

The fake supplier has a helper endpoint:

```bash
curl -sS -X POST "$FAKE_SUPPLIER_URL/v1/send-sms" \
  -H "Content-Type: application/json" \
  -d "{
    \"supplier_sms_id\":\"local-sms-1\",
    \"phone_number\":\"$PHONE_NUMBER\",
    \"phone_from\":\"Telegram\",
    \"text\":\"Your Telegram code is 12345\"
  }"
```

If the fake supplier server was not started with `SMSBRIDGE_SUPPLIER_API_KEY`, it returns the manual payload. Post that payload directly:

```bash
curl -sS -X POST "$BASE_URL/supplier/v1/sms" \
  -H "Authorization: Bearer $SUPPLIER_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"supplier_sms_id\":\"local-sms-1\",
    \"phone_number\":\"$PHONE_NUMBER\",
    \"phone_from\":\"Telegram\",
    \"text\":\"Your Telegram code is 12345\"
  }"
```

For local smoke testing, omitting `supplier_activation_id` is acceptable because the fake supplier helper and the supplier SMS endpoint can match the active activation by phone number. In production supplier integrations, prefer sending the real supplier activation id.

Verify the order moved to `sms_received`:

```bash
curl -sS "$BASE_URL/api/v1/orders/$ORDER_PUBLIC_ID" \
  -H "Authorization: Bearer $BUYER_TOKEN"
```

Expected:

- `status` is `sms_received`.
- `sms_code` is `12345`.
- `sms_text` is present.

## 8. Finish the Order

```bash
curl -sS -X POST "$BASE_URL/api/v1/orders/$ORDER_PUBLIC_ID/finish" \
  -H "Authorization: Bearer $BUYER_TOKEN"
```

Verify:

```bash
curl -sS "$BASE_URL/api/v1/orders/$ORDER_PUBLIC_ID" \
  -H "Authorization: Bearer $BUYER_TOKEN"

curl -sS "$BASE_URL/api/v1/wallet/transactions?limit=20" \
  -H "Authorization: Bearer $BUYER_TOKEN"

curl -sS "$BASE_URL/admin/suppliers/$SUPPLIER_ID/transactions" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

Expected:

- Order status is `completed`.
- Buyer wallet history contains `hold` and `capture`.
- Supplier transaction history contains a `reward`.

## 9. Cancel and Release Smoke Check

Create a second order, then cancel it before SMS:

```bash
ORDER2=$(curl -sS -X POST "$BASE_URL/api/v1/orders" \
  -H "Authorization: Bearer $BUYER_TOKEN" \
  -H "Idempotency-Key: local-order-cancel-1" \
  -H "Content-Type: application/json" \
  -d '{"service_code":"telegram","country_iso2":"ID","operator":null}')

ORDER2_PUBLIC_ID=$(echo "$ORDER2" | jq -r .public_id)

curl -sS -X POST "$BASE_URL/api/v1/orders/$ORDER2_PUBLIC_ID/cancel" \
  -H "Authorization: Bearer $BUYER_TOKEN"
```

Expected:

- Order status becomes `cancelled`.
- Buyer wallet hold is refunded.
- Reservation-enabled supplier release callback is attempted.

Check release retry visibility:

```bash
curl -sS "$BASE_URL/admin/supplier-release-retries" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

If the fake supplier is reachable, there should usually be no pending retry for this cancellation. If release fails, a retry job appears and the buyer refund still succeeds.

## 10. Optional Smoke Script

A helper script is available:

```bash
python tools/local_e2e_smoke.py
```

Defaults:

- `BASE_URL=http://localhost:8000`
- `FAKE_SUPPLIER_URL=http://localhost:8010`
- `RESERVATION_URL_FOR_BACKEND=http://fake-supplier:8010/v1/reservations`
- `ADMIN_EMAIL=admin@smsbridge.local`
- `BUYER_EMAIL=user@smsbridge.local`
- `LOCAL_E2E_PASSWORD=change-me`
- `LOCAL_E2E_TIMEOUT_SECONDS=15`
- `LOCAL_E2E_RUN_ID=<random>`

The script is for local operator convenience only and is not part of CI.
It prints each step name and exits non-zero on the first failed step. It does not print bearer tokens or supplier API keys.

## Current Limits

- Real payment provider integrations are intentionally deferred.
- Cryptomus/Payssion are planned future payment provider adapters, not implemented.
- Local payment testing uses `manual_test` and the admin `manual-complete` endpoint.
- Local supplier testing uses the fake supplier server.
- Provider webhook processing is still skeleton-only; external provider SMS currently relies on polling.
