# Implementation Readiness Assessment

> **Purpose**: Gate document. Implementation may only begin after all items below are resolved. 
> **Date**: 2026-08-28

---

## 1. Confirmed Assumptions

| # | Assumption | Verification |
|---|-----------|--------------|
| 1 | Razorpay has no direct "retry failed payment" endpoint | ✅ Confirmed — `pay_xxx` in `failed` is terminal. Recovery via new Order or Payment Link |
| 2 | Webhook signature uses HMAC-SHA256 on raw body | ✅ Confirmed — `X-Razorpay-Signature` header, webhook secret as key |
| 3 | Webhook dedup header exists | ✅ Confirmed — `X-Razorpay-Event-Id` in HTTP headers only |
| 4 | Webhooks are at-least-once delivery | ✅ Confirmed — duplicates possible, must dedup |
| 5 | Rate limit is approximately 100 req/min | ✅ Confirmed (approximate, from official error docs) |
| 6 | Payment Links limited to 30 in test mode | ✅ Confirmed |
| 7 | Orders have 3 states only (created/attempted/paid) | ✅ Confirmed |
| 8 | Payment Links have 5 states (created/partially_paid/paid/cancelled/expired) | ✅ Confirmed |
| 9 | `receipt` and `reference_id` do NOT provide idempotent replay | ✅ Confirmed — duplicates throw 400, not cached response |
| 10 | Test mode supports webhook delivery | ✅ Confirmed — separate webhook secret in test dashboard |
| 11 | SMS/Email notifications suppressed in test mode | ✅ Confirmed |
| 12 | Webhook event name is `payment_link.paid` (underscore) | ✅ Confirmed |
| 13 | Invoice API exists and is functional | ✅ Confirmed — full CRUD + notify + lifecycle |
| 14 | Payment error fields: `error_code`, `error_description`, `error_source`, `error_step`, `error_reason` | ✅ Confirmed |
| 15 | No global `Idempotency-Key` header for Orders/Payment Links | ✅ Confirmed — only Payouts/Refunds/Transfers have idempotency headers |

---

## 2. Rejected Assumptions

| # | Original Assumption | Reality |
|---|---------------------|---------|
| 1 | `receipt` provides idempotent Order creation | **WRONG** — duplicate `receipt` throws `400 Bad Request`, does not return existing order |
| 2 | `reference_id` provides idempotent Payment Link creation | **WRONG** — same behavior as `receipt` |
| 3 | Global `Idempotency-Key` header works for all POST requests | **WRONG** — only `X-Payout-Idempotency`, `X-Refund-Idempotency`, `X-Transfer-Idempotency` exist |
| 4 | Orders can expire or be cancelled | **WRONG** — Orders only have 3 states: `created`, `attempted`, `paid` |
| 5 | `callback_method` can be POST | **WRONG** — must be `"get"` when `callback_url` is provided |
| 6 | `expire_by` accepts any future timestamp | **WRONG** — must be ≥ 15 minutes in the future |
| 7 | Unlimited Payment Links in test mode | **WRONG** — hard limit of 30 per business |

---

## 3. Unresolved Questions

| # | Question | Impact | Current Decision |
|---|----------|--------|-----------------|
| 1 | **AI Provider for failure classification** | Low — deterministic rules are primary | Proceed with deterministic rule-based NLP for MVP. No external LLM dependency required for core decision engine. AI can be added later for explanation generation. |
| 2 | **Deployment target for demo** | Medium — affects setup time | Default to Docker Compose. Fallback: local execution with PostgreSQL. |
| 3 | **Team size** | Low — scope already defined for 2-4 students | Proceed with defined scope regardless. |
| 4 | **Exact Razorpay error reason strings** | Low — mapping is provisional | Refine after running first test-mode transactions. The adapter has a fallback `UNKNOWN` category. |
| 5 | **Payment Link test-mode 30-link limit management** | Medium — affects demo | Strategy: reuse links where possible. For benchmark, use synthetic simulation (not real API calls). Reserve real links for demo workflow. |

---

## 4. Architecture Decisions

### 4.1 Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Backend | **Python 3.13 + FastAPI** | Typed (Pydantic), async, auto OpenAPI docs, installed on system |
| Database | **PostgreSQL** | ACID transactions for state machine, FK constraints, JSONB |
| ORM | **SQLAlchemy 2.0 + Alembic** | Typed models, migrations, async support |
| Frontend | **React + TypeScript + Tailwind CSS** | Professional fintech UI, type safety |
| Node.js | **v22.14** (installed) | Frontend build tooling |
| Auth | **JWT (PyJWT) + bcrypt** | Lightweight, stateless tokens |
| Background | **In-process async workers** (asyncio) | No external queue needed for MVP |
| Cache | **In-process LRU** | No Redis needed for MVP workload |

### 4.2 Internal Action Naming

| Internal Action | Execution Implementation | Razorpay API |
|----------------|-------------------------|--------------|
| `RETRY` | `RETRY_PAYMENT_OPPORTUNITY` | Create new Payment Link (`POST /v1/payment_links`) or new Order (`POST /v1/orders`) |
| `NEW_PAYMENT_LINK` | `CREATE_PAYMENT_LINK` | `POST /v1/payment_links` |
| `REMINDER` | `SEND_REMINDER` | Log intended communication (test mode) or `POST /v1/invoices/:id/notify_by/email` for invoices |
| `ESCALATE` | `LOG_ESCALATION` | Internal record only |
| `STOP` | `CLOSE_CASE` | No external API call |

### 4.3 Architecture Style

**Modular monolith**. Single FastAPI process with logically separated modules:

```
backend/
├── app/
│   ├── api/           # REST endpoints
│   ├── auth/          # JWT + RBAC
│   ├── cases/         # RevenueRiskCase model, state machine
│   ├── decisions/     # ENR scoring, action ranking
│   ├── economics/     # Cost, probability, friction models
│   ├── policies/      # Deterministic policy engine
│   ├── actions/       # Action dispatcher
│   ├── razorpay/      # Razorpay adapter (isolated)
│   ├── webhooks/      # Webhook receiver, verification, dedup
│   ├── evaluation/    # Benchmark gen, baselines, evaluator
│   ├── audit/         # Audit log
│   ├── jobs/          # Background workers
│   ├── database/      # SQLAlchemy models, migrations
│   └── shared/        # Config, errors, types, rate limiting, cache
frontend/
├── src/
│   ├── pages/         # 6 priority views
│   ├── components/    # Shared UI
│   ├── api/           # Typed API client
│   ├── hooks/         # React hooks
│   └── types/         # TS types matching Pydantic schemas
```

### 4.4 Economic Model Units

All monetary values in **paise** (integer). All ENR calculations return **paise**.

| Term | Unit | Source Label |
|------|------|-------------|
| V (Recoverable Value) | Paise (₹ × 100) | From case `amount_at_risk` |
| P(success) | Probability [0, 1] | SYNTHETIC ASSUMPTION (labeled) |
| C (Action Cost) | Paise | CONFIGURED (merchant-adjustable) |
| F (Friction Cost) | Paise (monetary equivalent) | CONFIGURED (documented conversion) |
| D (Risk Penalty) | Paise (monetary equivalent) | CONFIGURED (documented conversion) |
| ENR | Paise | Computed: `P × V - C - F - D` |

If friction/risk cannot honestly be converted to paise, they become separate utility components with documented normalization.

---

## 5. MVP Boundary

### DEEP / REAL PATH (Primary)

**FAILED PAYMENT RECOVERY**
- Real Razorpay Test Mode integration
- Real webhook flow (payment.failed → case → decision → Payment Link → payment_link.paid → recovered)
- Real state machine transitions
- Real action execution via Razorpay API
- Real verified outcome via webhook
- Real audit trail
- Real failure handling (duplicate, out-of-order, timeout, 429, hard decline → STOP)

### SECONDARY (Simulated outcomes)

**ABANDONED CHECKOUT**
- Synthetic events (no native Razorpay "cart abandoned" webhook)
- Same economic engine evaluates ENR
- Same state machine
- Payment Link creation is real if triggered
- Outcome may be simulated for benchmark purposes

### TERTIARY (Benchmark only)

**OVERDUE RECEIVABLES**
- Synthetic benchmark cases
- Same economic engine
- Invoice API integration deferred unless trivially addable
- Purpose: prove the SAME decision engine works across heterogeneous case types

### EXPLICITLY OUT OF SCOPE

- Custom payment rails
- Real card storage / PCI-DSS scope
- Production banking integration
- Autonomous financial transfers
- Multi-agent framework / LLM chain
- Vector database / RAG / embeddings
- Complex microservices / Kafka / K8s
- Real SMS/WhatsApp sending
- File uploads (unless CSV import becomes needed)
- Subscription APIs
- Multi-merchant optimization
- Reinforcement learning
- Production communications infrastructure

---

## 6. Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| Python 3.13 | ✅ Installed | |
| Node.js 22.14 | ✅ Installed | |
| PostgreSQL | ❓ Need to verify/install | Check if available locally or plan Docker |
| Razorpay Test API Keys | ❓ Need user to provide | Store in `.env`, never in source |
| Razorpay Test Webhook Secret | ❓ Need user to configure | Dashboard → Test Mode → Webhooks |

---

## 7. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| 30 Payment Link test-mode limit exhausted during demo | Medium | High | Reserve links for demo; use synthetic simulation for benchmarks |
| Razorpay rate limit hit during benchmark | Low | Medium | Benchmark uses synthetic simulation, not real API calls |
| Error reason taxonomy doesn't match test-mode responses | Medium | Low | Fallback `UNKNOWN` category; refine after first test transactions |
| Webhook delivery delay in test mode | Low | Low | Polling fallback via `GET /v1/payments/:id` |
| PostgreSQL not available locally | Medium | Medium | Docker Compose includes PostgreSQL service |

---

## 8. Implementation Phases (Updated)

| Phase | Description | Depends On |
|-------|-------------|------------|
| **0** | ✅ Razorpay Contract Verification (this document) | — |
| **1** | Database schema, SQLAlchemy models, Alembic migrations | PostgreSQL |
| **2** | Case state machine + deterministic policy engine | Phase 1 |
| **3** | Economic decision engine (ENR, probability, costs) | Phase 1 |
| **4** | Razorpay adapter + webhook handler (signature, dedup) | Phase 1 |
| **5** | Action dispatcher + approval gate | Phases 2, 3, 4 |
| **6** | Evaluation system (benchmark gen, baselines, evaluator) | Phases 2, 3 |
| **7** | Auth (JWT), RBAC, rate limiting, error categories | Phase 1 |
| **8** | Backend API endpoints (REST, typed, paginated) | Phases 2-7 |
| **9** | Frontend (6 priority views) | Phase 8 |
| **10** | Failure testing (10 scenarios) | Phases 2-8 |
| **11** | Consistency audit | All phases |
| **12** | 5-minute demo rehearsal | All phases |

---

## 9. Gate Verdict

| Gate Item | Status |
|-----------|--------|
| All Razorpay endpoints verified | ✅ |
| No hypothetical retry API assumed | ✅ |
| Rate limits configuration-driven | ✅ |
| Idempotency per-operation verified | ✅ |
| Webhook dedup mechanism verified | ✅ |
| Recovery flow uses only verified APIs | ✅ |
| Economic model units coherent | ✅ |
| MVP boundary defined | ✅ |
| Test mode constraints documented | ✅ |
| Failure category mapping provisional (acceptable) | ✅ |

> **GATE PASSED**: Implementation may proceed to Phase 1.
