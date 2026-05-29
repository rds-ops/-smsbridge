# Fake Supplier Server

This is a local/dev-only HTTP server for testing supplier reservation callbacks. It is not imported by production business logic.

## Run With Docker Compose

```bash
docker compose --profile dev up fake-supplier
```

The server listens on:

```text
http://localhost:8010
```

Use this reservation URL on a test supplier:

```text
http://fake-supplier:8010/v1/reservations
```

or from the host:

```text
http://localhost:8010/v1/reservations
```

## Reservation Endpoint

```http
POST /v1/reservations
Idempotency-Key: sb-order-example
Content-Type: application/json
```

The same idempotency key and same body returns the same reservation. The same key with a different body returns `409`.

## SMS Helper

```http
POST /v1/send-sms
```

If `SMSBRIDGE_BASE_URL` and `SMSBRIDGE_SUPPLIER_API_KEY` are set, the fake server posts to `/supplier/v1/sms`. Otherwise it returns the payload needed for manual testing.
