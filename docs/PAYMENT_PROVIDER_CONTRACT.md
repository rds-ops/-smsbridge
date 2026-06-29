# Payment Provider Contract

Draft / internal. This document defines the backend contract for future real payment providers such as Payme, Click, or crypto rails. It does not enable any real provider by itself.

Current readiness: real payments are not ready. The implemented system supports `manual_test` payment intents, admin manual completion, an internal webhook foundation, idempotent wallet crediting, and read-only reconciliation visibility.

## 1. Current Internal Payment Model

Core tables:

- `payment_intents`: buyer deposit intent lifecycle.
- `payment_webhook_events`: webhook/event deduplication and processing status.
- `wallet_transactions`: buyer wallet ledger. Deposit credits from payment intents are linked by `payment_intent_id`.

Current buyer flow:

1. Buyer creates a payment intent with `POST /api/v1/payment-intents`.
2. The only enabled provider is `manual_test`.
3. Creating an intent does not credit the wallet.
4. Admin may complete a `manual_test` intent with `POST /admin/payment-intents/{id}/manual-complete`.
5. The same payment success path used by internal webhooks credits the wallet exactly once.

Implemented statuses:

- `created`
- `pending`
- `succeeded`
- `failed`
- `cancelled`
- `expired`

Allowed webhook-driven transitions:

- `created -> pending`
- `created -> failed`
- `created -> cancelled`
- `pending -> succeeded`
- `pending -> failed`
- `pending -> cancelled`

Terminal reversals are rejected or ignored. For example, `succeeded -> failed` must not mutate wallet balance.

Current webhook foundation:

- Endpoint: `POST /internal/payment-webhooks/{provider}`
- Auth: shared `X-Internal-Webhook-Secret`
- Deduplication: provider + external event id, or provider + deterministic payload hash fallback
- Wallet credit: only when an intent transitions into `succeeded`
- Ledger: creates `WalletTransaction(type="deposit")`
- Idempotency: `wallet_transactions.payment_intent_id` has a unique non-null index, so one payment intent can create at most one wallet deposit transaction
- Visibility: `last_webhook_at`, `last_webhook_event_id`, `last_webhook_status`, `last_webhook_error`, and `failed_reason` are stored on the payment intent
- Reconciliation: `GET /admin/payment-intents/reconciliation`

Current limitations:

- No real payment provider is enabled.
- `payme`, `click`, and `crypto_usdt` are allowlist placeholders, not usable providers.
- Generic internal webhook secret is not sufficient for real provider traffic.
- Provider-specific signatures are not implemented.
- Provider-specific amount/currency validation is not implemented.
- Provider-specific checkout/session creation is not implemented.
- Chargeback, refund, and dispute lifecycles are not implemented.

## 2. Provider Adapter / Handler Contract

Each real payment provider must have an explicit backend handler. A real provider must not be wired directly to the generic internal webhook parser without provider-specific validation.

Required handler responsibilities:

1. Create checkout/payment session.
   - Accept an existing internal `PaymentIntent`.
   - Create a provider-side payment/session/invoice.
   - Store safe provider identifiers on the intent, usually `provider_reference` and safe metadata.
   - Return buyer-safe checkout information, such as redirect URL or payment instructions.

2. Verify provider-specific webhook signature.
   - Use the provider's official signature/HMAC/token scheme.
   - Reject missing, invalid, replayed, or stale signatures before parsing status.
   - Do not rely only on `X-Internal-Webhook-Secret`.
   - Do not log secrets, full headers, raw payloads, or signature material.

3. Parse provider event.
   - Extract stable external event id when available.
   - Extract provider payment/reference id.
   - Extract provider status.
   - Extract paid amount and currency.
   - Extract failure/cancel reason if safe.
   - Sanitize diagnostic fields before storing.

4. Map provider status to internal status.
   - Provider-specific statuses must map explicitly to `pending`, `succeeded`, `failed`, or `cancelled`.
   - Unknown or unsupported statuses must be recorded as ignored/diagnostic events and must not mutate wallet balance.
   - Provider status mapping must be covered by tests with provider fixtures.

5. Validate target payment intent.
   - Find intent by internal public id and/or provider reference.
   - Ensure intent.provider matches the handler provider.
   - Unknown intent events must not credit wallet.
   - Unknown intent events should be recorded safely for operator investigation.

6. Validate amount and currency.
   - Provider-paid amount must exactly match internal `payment_intents.amount` after provider-specific minor-unit conversion.
   - Provider currency must match internal `payment_intents.currency`.
   - Wrong amount or currency must not credit wallet.
   - Wrong amount or currency should be visible to admins as a sanitized payment webhook/intent error.

7. Deduplicate event.
   - Use provider event id when available.
   - If a provider lacks event ids, derive a deterministic hash from stable provider reference, status, amount, currency, and event timestamp where safe.
   - Duplicate succeeded events must not double-credit wallet.

8. Credit wallet exactly once.
   - Only transition into `succeeded` should call wallet crediting.
   - Status transition, webhook event record, wallet balance update, and wallet transaction insert should happen atomically in one database transaction.
   - If wallet credit fails, do not leave the payment intent marked `succeeded`.

9. Store safe provider references and diagnostics.
   - Store provider payment id, event id, and sanitized error/reason fields.
   - Do not store raw provider payloads unless a future explicit redaction/archive policy is approved.
   - Never store provider API secrets, signature keys, bearer tokens, card data, or sensitive personal data in logs or metadata.

## 3. Provider-Specific Rules

No provider may go live unless all of these are true:

- Provider credentials are loaded from production secret management, not hardcoded or committed.
- Webhook signature verification is implemented and tested.
- Checkout/session creation stores a provider reference before the provider can send success events.
- Event id or deterministic deduplication is implemented.
- Amount validation is implemented.
- Currency validation is implemented.
- Status mapping is explicit and tested.
- Unknown events are ignored or recorded without wallet mutation.
- Failed/cancelled events do not credit wallet.
- Duplicate succeeded events do not double-credit wallet.
- A succeeded event for an already terminal non-succeeded intent is ignored or escalated without wallet mutation.
- A succeeded event for an expired intent has a documented provider-specific policy before wallet mutation is allowed.

The generic `/internal/payment-webhooks/{provider}` endpoint is an internal foundation. For real providers, either:

- add provider-specific webhook endpoints that verify signatures and then call the shared transition/credit helper, or
- keep the internal endpoint behind an adapter/gateway that performs provider-specific verification before forwarding a normalized event.

## 4. Checkout / Session Creation Contract

Future real provider checkout creation should follow this shape:

1. Buyer creates an internal payment intent.
2. Backend validates provider is enabled for real payments.
3. Backend calls provider adapter to create provider checkout/session.
4. Adapter stores:
   - `payment_intents.provider_reference`
   - safe checkout/session ids in `payment_intents.metadata`
   - optional expiration/checkout URL fields if a future schema adds them
5. Backend returns buyer-safe checkout details.

Rules:

- Payment intent creation alone must not credit wallet.
- Provider session creation must be idempotent per payment intent.
- If provider session creation fails, intent should remain `created` or transition to `failed` only through a documented policy.
- Buyer response must not expose provider secrets or internal diagnostics.

## 5. Webhook Processing Contract

Provider webhook processing should run in this order:

1. Authenticate/verify signature.
2. Parse and sanitize event.
3. Deduplicate by provider event id or stable fallback hash.
4. Locate payment intent.
5. Validate provider reference.
6. Validate amount.
7. Validate currency.
8. Map provider status.
9. Apply allowed internal transition.
10. If transitioning to `succeeded`, credit wallet exactly once through the ledger path.
11. Store webhook event and safe visibility fields.
12. Commit atomically.

Rejected cases:

- invalid signature
- unknown provider
- unknown event status
- unknown payment intent
- provider mismatch
- wrong amount
- wrong currency
- invalid internal status transition
- duplicate event

Only duplicate/ignored diagnostic records may be stored for rejected cases. Wallet balance must not change.

## 6. Operator Runbook

### Provider shows paid but wallet not credited

1. Check admin payment intent detail.
2. Check `GET /admin/payment-intents/reconciliation`.
3. Confirm provider event id, provider reference, amount, and currency.
4. Confirm whether webhook was received, rejected, ignored, or duplicated.
5. If provider proof is valid and internal state is inconsistent, use a documented manual repair process. Do not directly edit wallet balance without a `WalletTransaction`.
6. Record operator action in audit/risk/incident notes.

### Wallet credited but provider payment not succeeded

1. Treat as high severity.
2. Check payment intent status and linked `WalletTransaction`.
3. Check provider dashboard/reference.
4. Do not reverse by direct DB mutation.
5. Use a future approved refund/reversal ledger flow or manual accounting procedure.
6. Mark incident for finance review.

### Duplicate webhook

1. Confirm same provider event id or same payload hash.
2. Verify only one `WalletTransaction` exists for the payment intent.
3. No repair is needed if the intent and wallet ledger are consistent.

### Wrong amount

1. Do not credit wallet.
2. Record sanitized diagnostic state.
3. Check provider dashboard.
4. Decide whether to cancel, fail, refund externally, or ask buyer to create a corrected intent.
5. Do not manually top up unless a finance-approved ledger action is recorded.

### Unknown payment intent

1. Do not credit wallet.
2. Check whether provider reference was stored during checkout/session creation.
3. If provider shows a real paid transaction, escalate to finance/operator review.
4. Do not create a wallet deposit without linking it to a valid internal intent or approved manual adjustment.

### Expired payment later succeeds

Policy is not implemented yet. Before real provider launch, define provider-specific behavior:

- accept late success and credit if provider settlement is final, or
- reject/mark for manual refund if the provider supports refund, or
- hold for manual review.

Until this policy exists, real provider events for expired intents must not silently credit wallet.

### Refund / chargeback / dispute

Not implemented. Before real provider launch, define:

- whether buyer wallet balance can be debited after deposit
- what happens if funds were already spent on orders
- whether disputes create held balances, negative risk flags, or admin-only debt records
- required audit and finance approvals

## 7. Required Tests Before First Real Provider

Provider-specific tests must cover:

- checkout/session creation stores provider reference safely
- valid signature accepted
- missing/invalid signature rejected
- known pending/succeeded/failed/cancelled events map correctly
- unknown provider event is ignored without wallet mutation
- unknown payment intent does not credit wallet
- wrong amount does not credit wallet
- wrong currency does not credit wallet
- duplicate event does not double-credit wallet
- alternate succeeded event after already-succeeded intent does not double-credit wallet
- invalid terminal reversal does not credit or mutate incorrectly
- wallet credit failure rolls back payment intent success
- no raw secret, signature, or unsafe payload is logged or returned

## 8. Readiness Status

Current status:

- Local/manual payment testing: ready through `manual_test`.
- Friendly buyer testing with admin/manual funding: mostly ready after browser QA.
- Real payment provider integration: not ready.

Blockers before real payments:

- choose first provider
- implement provider-specific checkout/session creation
- implement provider-specific webhook signature verification
- implement provider-specific amount/currency/status validation
- define expired-late-success policy
- define refunds, chargebacks, and dispute policy
- define production secret management for provider credentials
- run provider sandbox tests and reconciliation drills
