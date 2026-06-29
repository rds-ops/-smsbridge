# Production Backend Runbook

Draft/internal. This document records the backend safety posture before connecting external suppliers, real buyers, real payment providers, or real SMS providers.

Last audit: BE-31, after RC-1 verification on 2026-06-27.

## 1. Current Status

Backend release-candidate verification passed in RC-1:

- backend image build passed
- Alembic upgrade/head/current passed with single head `0022_obs_index_audit`
- full backend suite passed: `283 passed, 1 warning`
- frontend build and local E2E smoke passed

Production launch is still not approved. Real payment providers and real SMS providers remain disabled/deferred.

## 2. Production Environment Requirements

Use `ENVIRONMENT=production` or `ENVIRONMENT=staging` for production-like deployments.

Production-like startup rejects:

- default or short `SECRET_KEY`
- default `ADMIN_SEED_PASSWORD`
- empty/default `INTERNAL_WEBHOOK_SECRET`
- wildcard `CORS_ORIGINS`

Required production values:

- `SECRET_KEY`: unique random value, at least 32 characters
- `ADMIN_SEED_PASSWORD`: not `change-me` if seed is used
- `INTERNAL_WEBHOOK_SECRET`: unique random value
- `CORS_ORIGINS`: exact HTTPS frontend/admin origins, comma-separated
- `DATABASE_URL`: production PostgreSQL URL
- `REDIS_URL`: production Redis URL

Do not run production from `.env.example`.

## 3. Auth and Session Policy

Implemented:

- JWT access and refresh tokens
- refresh sessions stored in PostgreSQL
- refresh token `jti` validation
- logout for current refresh session
- logout-all for all current-user refresh sessions
- admin revoke-all for a specific user's refresh sessions
- buyer managed API keys with scopes, revoke, usage, and `last_used_at`
- legacy buyer API key compatibility
- supplier API keys stored as hashes
- admin role checks

Compatibility note:

- Refresh tokens issued before BE-32 do not contain a `jti` and are rejected by `/auth/refresh`.
- Access tokens remain stateless and continue to work until expiry.
- Admin session revocation does not invalidate already-issued access tokens; it prevents future refresh for the target user.

Remaining auth gaps:

- no email verification
- no per-account login lockout
- no password reset or forced password rotation flow
- refresh tokens are not rotated on every refresh; the active refresh session is reused until logout, logout-all, or expiry

Admin compromised-account process:

1. Confirm the target user id from admin user detail, risk, or request-log views.
2. Call `POST /admin/users/{user_id}/sessions/revoke-all`.
3. Record the incident context in internal operator notes or risk actions.
4. Treat active access tokens as valid until their normal expiry; do not assume immediate access-token invalidation.
5. If credential compromise is suspected, coordinate an out-of-band password reset/rotation because password reset is not implemented yet.

## 4. Secret Handling

Do not log:

- bearer tokens
- buyer API keys
- supplier API keys
- supplier reservation bearer secrets
- internal webhook secrets
- payment/provider raw payloads containing secrets
- SMS text in request logs

Current safeguards:

- request logs store metadata only
- API request logging does not store request bodies or auth headers
- supplier reservation bearer secret is redacted from supplier admin audit metadata
- supplier and buyer API keys are stored as hashes and raw keys are returned only on creation/regeneration

Known gap before real suppliers/providers:

- `reservation_auth_secret_encrypted` and provider credential fields are not backed by a formal KMS/encryption-at-rest design in application code.
- Treat this as a blocker before scaling real supplier/provider secret storage beyond a controlled sandbox.

## 5. CORS and Network Exposure

Production-like deployments must use exact trusted origins.

Allowed example:

```text
CORS_ORIGINS=https://app.smsbridge.com,https://admin.smsbridge.com
```

Forbidden:

```text
CORS_ORIGINS=*
```

Current backend does not configure TrustedHost middleware. Put the API behind a reverse proxy/load balancer that enforces expected hostnames, TLS, body limits, and timeout policy.

## 6. Internal Webhooks

Implemented:

- `/internal/provider-webhooks/{provider_code}` skeleton
- `/internal/payment-webhooks/{provider}` foundation
- shared `X-Internal-Webhook-Secret` guard

Current limitations:

- provider webhooks do not process real provider events
- payment webhooks do not implement real provider signatures
- shared-secret auth is not sufficient for real external payment providers

Policy:

- Keep internal webhook endpoints private or protected by network controls.
- Do not connect real providers until provider-specific signature verification and event mapping exist.

## 7. Rate Limiting

Implemented:

- Redis-backed fixed-window rate limiting
- identity-aware buckets for buyer API keys, users, suppliers, and IP fallback
- tier-based settings
- fail-open behavior if Redis is unavailable

Production notes:

- Fail-open avoids total API outage but weakens abuse protection during Redis incidents.
- Tune anonymous/user/supplier/admin limits before broader beta.
- Health endpoints are bypassed.

## 8. Observability and Operations

Implemented:

- `/health/live`
- `/health/ready`
- request id middleware and `X-Request-ID`
- API request logs with user/supplier/buyer key attribution
- audit logs for many admin actions
- admin ops summary
- payment and payout reconciliation visibility
- supplier release retry visibility
- risk summaries and manual risk actions
- operational cleanup dry-run

Missing before production launch:

- external alerting
- metrics dashboard outside admin UI
- centralized log shipping
- backup/restore verification
- incident response runbook
- accounting-grade reporting

## 9. Data Safety

Implemented:

- buyer prices hide `provider_cost`
- buyer wallet and supplier balances have non-negative DB checks
- wallet/supplier financial movements use ledgers
- payment intent wallet crediting is idempotent by `wallet_transactions.payment_intent_id`
- supplier release failures are retried durably

Known limitations:

- reconciliation views are read-only
- automatic repair is not implemented
- real payment chargeback/refund lifecycle is not implemented
- real provider reconciliation is not implemented

## 10. Go/No-Go Summary

Friendly buyers with manual/mock systems:

- Backend: go after visual browser QA is recorded.
- Risk: acceptable for small trusted beta with monitoring.

First real supplier sandbox:

- Backend: go for sandbox only after contract/KYC process and supplier sandbox signoff.
- Production onboarding: no-go until KYC/support policy, secret handling policy, supplier UI visibility, and external payout execution process are complete.

Real payments:

- No-go until provider-specific verification, event mapping, reconciliation/runbook, and legal/accounting policy are implemented.

Real SMS providers:

- No-go until a real adapter, price/stock freshness, cancellation semantics, credential rotation, and reconciliation are implemented.

Public launch:

- No-go until monitoring/alerting, production runbooks, legal/support processes, load/security verification, and real integration policies are complete.
