# SMSBridge — Core Rules & Roadmap

## Review of Current Architecture Map

Текущий `ARCHITECTURE_MAP.md` уже очень хороший для MVP-проекта.

Главное:
- документ реально описывает flow системы;
- видны сильные и слабые места;
- понятны P0/P1/P2;
- архитектура уже выглядит как marketplace system, а не просто CRUD API.

Что стоит улучшить позже:
- добавить sequence diagrams для order lifecycle;
- отдельно описать provider routing strategy;
- отдельно описать anti-abuse architecture;
- отдельно описать scaling strategy;
- добавить diagram для wallet/accounting flow.

Но прямо сейчас документ уже достаточно хорош, чтобы:
- планировать разработку;
- ставить задачи Codex;
- онбордить новых разработчиков;
- не потерять контроль над системой.

Ничего критичного переписывать в `ARCHITECTURE_MAP.md` сейчас не нужно.

---

# CORE_RULES.md

## Purpose

Этот документ — конституция проекта.

Любая новая фича, endpoint, worker, payment flow или provider integration НЕ должны нарушать эти правила.

Если новая логика ломает одно из правил — архитектуру нужно пересматривать.

---

# 1. Money Integrity Rules

## Rule 1.1

Wallet balance никогда не может стать отрицательным.

Обязательно:
- DB constraints
- transactional updates
- row locking
- idempotent financial operations

---

## Rule 1.2

Held balance никогда не может стать отрицательным.

---

## Rule 1.3

Каждая финансовая операция должна иметь ledger record.

Нельзя:
- менять balance напрямую без transaction record.

Все движения денег должны проходить через:
- hold
- capture
- refund
- deposit
- adjustment
- payout

---

## Rule 1.4

Все financial actions должны быть idempotent.

Повторный запрос НЕ должен:
- списывать деньги дважды;
- делать двойной capture;
- делать двойной refund.

---

## Rule 1.5

Order creation и wallet mutation должны быть transactional.

Нельзя:
- успешно зарезервировать номер,
- но не создать order/wallet hold.

---

# 2. Order Lifecycle Rules

## Rule 2.1

Все order status transitions идут только через state machine.

Запрещено:

```python
order.status = "completed"
```

в random местах кода.

Все transitions проходят через:

```text
services/order_state.py
```

---

## Rule 2.2

Каждый order transition должен логироваться.

Минимум:
- old_status
- new_status
- timestamp
- actor/system
- reason

---

## Rule 2.3

Terminal states:
- completed
- cancelled
- expired
- refunded
- failed

Terminal state не может случайно перейти обратно в active state.

---

# 3. Number Reservation Rules

## Rule 3.1

Один номер не может принадлежать двум active orders одновременно.

---

## Rule 3.2

Supplier inventory должен быть real inventory.

Запрещено production-использование:

```text
_fake_supplier_phone
```

---

## Rule 3.3

Reservation logic должна быть concurrency-safe.

Обязательно:
- row locking
- transactions
- unique constraints
- active reservation checks

---

# 4. Pricing Rules

## Rule 4.1

Buyer никогда не видит:
- provider_cost
- supplier margin
- internal markup
- internal provider routing

---

## Rule 4.2

Final customer price фиксируется на order creation.

Даже если provider price изменится позже.

---

## Rule 4.3

Pricing logic должна быть centralized.

Запрещено:
- random markup calculations по проекту.

Все pricing calculations идут через:

```text
services/pricing.py
```

---

# 5. Security Rules

## Rule 5.1

Production environment никогда не запускается с:
- default SECRET_KEY
- default admin password
- debug settings

---

## Rule 5.2

Все internal callbacks должны быть authenticated.

Например:
- provider webhooks
- payment webhooks
- supplier callbacks

---

## Rule 5.3

Supplier API и admin API должны логироваться.

---

## Rule 5.4

Sensitive data не должна попадать:
- в public API
- в logs
- в frontend responses

---

# 6. Redis Rules

## Rule 6.1

Redis не хранит critical durable state.

Critical state хранится только в PostgreSQL.

Redis можно использовать для:
- rate limiting
- cache
- queues
- temporary locks
- idempotency cache

---

## Rule 6.2

Если Redis полностью очистится:
- деньги не должны потеряться;
- orders не должны ломаться.

---

# 7. API Rules

## Rule 7.1

Namespaces должны оставаться разделенными:

```text
/auth
/public
/api/v1
/supplier/v1
/admin
/internal
```

---

## Rule 7.2

Buyer API не должен использовать admin schemas.

---

## Rule 7.3

Public schemas и internal schemas должны быть раздельными.

---

# 8. Provider Rules

## Rule 8.1

Provider adapters должны быть isolated.

Каждый provider:
- get_number
- get_order_status
- cancel_order
- finish_order

через единый interface.

---

## Rule 8.2

Provider failure не должен ломать всю систему.

Provider errors должны быть isolated.

---

# 9. Scaling Rules

## Rule 9.1

Нельзя использовать in-memory rate limit для production.

---

## Rule 9.2

Workers должны быть concurrency-safe.

Polling tasks должны использовать:

```sql
FOR UPDATE SKIP LOCKED
```

---

# 10. Development Rules

## Rule 10.1

Новые фичи сначала:
1. architecture impact
2. implementation plan
3. only then code

---

## Rule 10.2

Codex не должен напрямую делать крупный refactor без architecture review.

---

## Rule 10.3

Сначала:
- correctness
- integrity
- safety

Потом:
- optimization
- scaling
- polish

---

# ROADMAP.md

# Phase 1 — Stabilize Core (P0)

## Goal

Сделать систему безопасной для денег, order lifecycle и concurrency.

## Tasks

### Security

- remove provider_cost from buyer API
- production secret guard
- production admin password guard
- validate provider types/statuses
- add supplier request logging

### Wallet & Orders

- add DB constraints for balances
- add explicit order state machine
- add order transition history
- add idempotency keys for order creation
- fix provider reservation vs wallet hold flow
- add transactional order creation wrapper

### Inventory

- remove fake supplier phone flow
- choose supplier reservation architecture:
  - exact inventory
  - reservation callback
- fix operator uniqueness issues
- improve inventory locking

### Redis & Concurrency

- replace in-memory rate limiting
- move rate limit to Redis
- add distributed throttling
- improve Celery polling locks

### SMS

- create generic sms_messages table
- normalize external provider SMS flow
- add internal webhook architecture

---

# Phase 2 — Marketplace Accounting (P1)

## Goal

Сделать полноценную marketplace accounting system.

## Tasks

### Payments

- payment intents
- deposit providers
- webhook verification
- idempotent deposits
- payment reconciliation

### Supplier Payouts

- payout requests
- supplier payout holds
- admin payout approval
- mark-paid flow
- payout ledger

### Stats

- real delivery rate
- provider success rate
- supplier performance metrics
- avg SMS time
- routing quality scores

### Buyer Transparency

- wallet transaction history
- payment history
- API key management
- multiple API keys
- scopes and labels

---

# Phase 3 — Real Provider Integration

## Goal

Подключить реальные provider integrations.

## Tasks

- implement real 5sim adapter
- implement SMS-Activate adapter
- implement Sms-man adapter
- provider sync jobs
- provider stock freshness
- provider reconciliation
- provider retry logic
- provider failover logic

---

# Phase 4 — Scaling & Reliability

## Goal

Подготовить систему к реальному трафику.

## Tasks

- distributed workers
- queue optimization
- DB indexing audit
- observability
- metrics dashboards
- tracing
- structured logging
- caching strategy
- background reconciliation jobs
- abuse prevention
- fraud/risk controls

---

# Phase 5 — Public API & Platform

## Goal

Сделать систему полноценной developer platform.

## Tasks

- public catalog API
- polished API docs
- SDK examples
- webhook subscriptions
- API usage analytics
- better admin dashboards
- provider analytics
- supplier onboarding flows
- moderation workflows

---

# Recommended Team Workflow

## Before Any New Feature

1. define architecture impact
2. define data model impact
3. define API impact
4. define concurrency risks
5. define money/integrity risks
6. only then implement

---

# Recommended Priority Order

Always prioritize:

1. money correctness
2. order correctness
3. inventory correctness
4. security
5. observability
6. scaling
7. UX polish

---

# Important Final Note

Current project state is NOT a failed architecture.

It is a realistic early-stage marketplace MVP with:
- decent service separation
- provider abstraction
- wallet ledger foundation
- supplier abstraction
- Dockerized infrastructure
- Celery worker architecture

The biggest current risk is not bad syntax.

The biggest risk is uncontrolled feature growth before stabilizing:
- money flow
- order lifecycle
- supplier inventory
- concurrency behavior
- pricing architecture.

If Phase 1 is completed correctly, the project can evolve into a production-grade SMS marketplace architecture instead of collapsing into AI-generated spaghetti.

