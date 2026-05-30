# API (Supplier) — Draft / Internal

This document describes the current supplier partner API as implemented in this repo. It is intended for internal/operator use and may change.

Base URL: `http(s)://<host>`

All supplier endpoints are under: `/supplier/v1/*`

## Authentication (Supplier API Key)

Supplier endpoints require:

`Authorization: Bearer <supplier_api_key>`

Notes:
- This is not a JWT. It is a supplier API key stored as a hash server-side.
- Missing/invalid credentials return `401` with `{"detail":"..."}`.
- Blocked/inactive suppliers are rejected with `403`.

## Endpoints

### Get supplier profile

`GET /supplier/v1/me`

Returns (current shape):
- `id`, `name`, `email`, `status`
- `reward_percent`
- `balance`, `held_balance`, `currency`

Example:
```bash
curl -sS "$BASE_URL/supplier/v1/me" \
  -H "Authorization: Bearer $SUPPLIER_API_KEY"
```

### List inventory

`GET /supplier/v1/inventory`

Returns rows for this supplier:
- `service_code`, `country_iso2`, `operator` (nullable)
- `available_count`
- optional metrics fields: `success_rate`, `avg_sms_time_seconds`
- `status`
- timestamps

Example:
```bash
curl -sS "$BASE_URL/supplier/v1/inventory" \
  -H "Authorization: Bearer $SUPPLIER_API_KEY"
```

### Update inventory (upsert)

`POST /supplier/v1/inventory/update`

Auth:
- Supplier must be active.

Body:
```json
{
  "items": [
    {
      "service_code": "telegram",
      "country_iso2": "ID",
      "operator": null,
      "available_count": 10,
      "success_rate": 95,
      "avg_sms_time_seconds": 20,
      "status": "active"
    }
  ]
}
```

Response:
```json
{ "updated": 1 }
```

Example:
```bash
curl -sS -X POST "$BASE_URL/supplier/v1/inventory/update" \
  -H "Authorization: Bearer $SUPPLIER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"items":[{"service_code":"telegram","country_iso2":"ID","operator":null,"available_count":10,"status":"active"}]}'
```

### Push SMS (supplier callback into smsbridge)

`POST /supplier/v1/sms`

Auth:
- Supplier must be active.

Body:
```json
{
  "supplier_sms_id": "your-message-id-123",
  "phone_number": "+628123456789",
  "phone_from": "Telegram",
  "text": "Your code is 12345",
  "supplier_activation_id": "optional-activation-id"
}
```

Response:
```json
{ "status": "SUCCESS", "duplicate": false }
```

Idempotency:
- `supplier_sms_id` is treated as an idempotency key per supplier.
- Re-sending the same `(supplier_id, supplier_sms_id)` returns `duplicate=true` and does not create duplicate SMS records.

Example:
```bash
curl -sS -X POST "$BASE_URL/supplier/v1/sms" \
  -H "Authorization: Bearer $SUPPLIER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"supplier_sms_id":"msg-1","phone_number":"+628123456789","text":"Your code is 12345","supplier_activation_id":"act-1"}'
```

## Supplier Reservation / Release Callbacks (Supplier-side expectations)

These are outbound calls from smsbridge to the supplier (supplier must host the endpoints). The detailed contract is documented in `docs/API_CALLBACKS.md`.

High level:
- Reservation callback is used when a supplier is configured with `reservation_enabled=true` (admin configuration).
- Release callback is best-effort on cancel/expire/fail and must not block buyer refunds.

Supplier requirements:
- HTTPS required for production deployments.
- Do not log secrets; do not return secrets in responses.
- Implement idempotency:
  - Same `Idempotency-Key` + same body must be safe/repeatable.
  - Same `Idempotency-Key` + different body should return `409 Conflict`.

## Security Notes

- Supplier API keys must never be sent via query params.
- Use `Authorization: Bearer ...` only.
- smsbridge request logging intentionally does not log request bodies or Authorization headers.
- Treat SMS `text` as sensitive; avoid logging it on the supplier side.

