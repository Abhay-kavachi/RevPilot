# RevPilot — Updated Implementation Plan (Post-Verification Gate)

## Gate Status: ✅ PASSED

Both required gate documents have been created and populated from **current official Razorpay documentation**:

- [23-razorpay-contract-verification.md](file:///c:/Users/abhay/OneDrive/Documents/Projects/RevPilot/docs/23-razorpay-contract-verification.md) — Every endpoint, webhook, and behavior verified
- [implementation-readiness.md](file:///c:/Users/abhay/OneDrive/Documents/Projects/RevPilot/docs/implementation-readiness.md) — Assumptions confirmed/rejected, architecture decisions, MVP scope, risks

---

## Critical Corrections Applied

### 7 False Assumptions Caught and Corrected

| # | What We Assumed | What's Actually True | Impact |
|---|----------------|---------------------|--------|
| 1 | `receipt` provides idempotent Order creation | Duplicate `receipt` → `400 Bad Request` error | Must pre-check locally before calling Create Order |
| 2 | `reference_id` provides idempotent Payment Link creation | Same — `400` error, not cached response | Must pre-check locally |
| 3 | Global `Idempotency-Key` header works for all POSTs | Only exists for Payouts, Refunds, Transfers | Application-level dedup for Orders & Links |
| 4 | Orders can expire or be cancelled | Only 3 states: `created` → `attempted` → `paid` | Cannot "cancel" an order; it stays `attempted` forever |
| 5 | `callback_method` can be POST | Must be `"get"` | Fixed in adapter |
| 6 | `expire_by` accepts any future timestamp | Must be ≥ 15 minutes in future | Enforce minimum in adapter |
| 7 | Unlimited Payment Links in test mode | Hard limit: 30 per business | Reserve for demo; benchmark uses simulation |

### Key Design Changes

1. **`RETRY` → `RETRY_PAYMENT_OPPORTUNITY`**: Internal action maps to creating a new Payment Link (primary) or new Order (alternative). Code and docs explicitly show this distinction.

2. **Three-Layer Idempotency**: Designed per-operation based on verified mechanisms (see [verification doc](file:///c:/Users/abhay/OneDrive/Documents/Projects/RevPilot/docs/23-razorpay-contract-verification.md#3-idempotency--per-operation)).

3. **Rate Limits**: Config-driven `RAZORPAY_RATE_LIMIT_PER_MINUTE` and `RAZORPAY_TARGET_RATE_PER_MINUTE` environment variables. Not hardcoded.

4. **Economic Model**: All terms in paise (₹ × 100). Probability tables labeled `SYNTHETIC ASSUMPTION`. No fake precision.

5. **MVP Scope Cut**: 
   - **DEEP**: Failed Payment Recovery (real Razorpay integration)
   - **SECONDARY**: Abandoned Checkout (synthetic events, same engine)
   - **TERTIARY**: Overdue Invoices (benchmark cases only)

6. **Frontend**: 6 priority views (cut from 9). Case Detail is the hero screen.

7. **No AI for decisions**: Deterministic economic engine. AI only for optional failure context classification.

---

## Readiness for Phase 1

All blockers are resolved:

| Requirement | Status |
|-------------|--------|
| Razorpay endpoints verified | ✅ |
| Recovery flows use only verified APIs | ✅ |
| Idempotency designed per-operation | ✅ |
| Rate limits configuration-driven | ✅ |
| Webhook dedup mechanism confirmed | ✅ |
| Economic model units coherent | ✅ |
| State machine defined | ✅ |
| MVP boundary set | ✅ |
| Test mode constraints documented | ✅ |

**Next step**: Upon your approval, I will begin **Phase 1 — Database schema, SQLAlchemy models, and Alembic migrations**.

---

## Remaining Open Items (Non-blocking)

1. **PostgreSQL availability** — will check/install or use Docker
2. **Razorpay test API keys** — you'll need to provide these in `.env`
3. **Error reason taxonomy** — provisional mapping, refined after first test transactions
