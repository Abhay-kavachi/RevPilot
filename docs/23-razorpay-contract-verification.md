# 23 — Razorpay Contract Verification Gate

> **Purpose**: Every Razorpay-specific assumption verified against **current official documentation** before implementation begins. No endpoint, event, or behavior is used in code unless it appears here as ✅ VERIFIED.
>
> **Last verified**: 2026-08-28

---

## 1. API Endpoints

### 1.1 Fetch Payment

| Field | Value |
|-------|-------|
| **Endpoint** | `GET https://api.razorpay.com/v1/payments/:id` |
| **Official Source** | https://razorpay.com/docs/api/payments/ |
| **Verified?** | ✅ VERIFIED |
| **Test Mode?** | ✅ Fully supported (`rzp_test_` keys) |
| **Our Usage** | Check payment status after action; read error fields for failure classification |
| **Auth** | HTTP Basic Auth (`KEY_ID:KEY_SECRET`) |
| **Required Params** | `id` (path param, e.g. `pay_xxx`) |
| **Key Response Fields** | `id`, `entity`, `amount`, `currency`, `status`, `order_id`, `method`, `error_code`, `error_description`, `error_source`, `error_step`, `error_reason`, `captured`, `email`, `contact`, `notes`, `fee`, `tax`, `created_at` |
| **Payment Statuses** | `created`, `authorized`, `captured`, `refunded`, `failed` |
| **Error Behavior** | 404 if ID not found. 401 if auth fails. Error fields populated when `status=failed` |
| **Idempotency** | N/A (GET request) |
| **Notes** | Optional: `expand[]=card`, `expand[]=emi`, `expand[]=offers` |

### 1.2 List Payments

| Field | Value |
|-------|-------|
| **Endpoint** | `GET https://api.razorpay.com/v1/payments` |
| **Official Source** | https://razorpay.com/docs/api/payments/ |
| **Verified?** | ✅ VERIFIED |
| **Pagination** | `count` (max 100, default 10) + `skip` (offset). Also `from`/`to` Unix timestamps |
| **Our Usage** | Batch status checks if needed |

### 1.3 Fetch Payments for an Order

| Field | Value |
|-------|-------|
| **Endpoint** | `GET https://api.razorpay.com/v1/orders/:id/payments` |
| **Official Source** | https://razorpay.com/docs/api/orders/ |
| **Verified?** | ✅ VERIFIED |
| **Our Usage** | Check all payment attempts against a retry order |

### 1.4 "Retry" a Failed Payment — DOES NOT EXIST

| Field | Value |
|-------|-------|
| **Endpoint** | **NO SUCH ENDPOINT** |
| **Official Source** | https://razorpay.com/docs/api/payments/ (confirmed by absence) |
| **Verified?** | ✅ VERIFIED as non-existent |
| **Our Usage** | **NOT USED** |
| **Recovery Flow** | A `pay_xxx` in `failed` state is terminal and immutable. Recovery via: (a) re-open checkout with same `order_id`, (b) create new Payment Link, (c) create new Order |

> **CRITICAL**: Our internal action `RETRY` maps to `RETRY_PAYMENT_OPPORTUNITY` — creating a new payment opportunity via a supported flow, NOT re-charging a failed payment entity.

### 1.5 Create Order

| Field | Value |
|-------|-------|
| **Endpoint** | `POST https://api.razorpay.com/v1/orders` |
| **Official Source** | https://razorpay.com/docs/api/orders/ |
| **Verified?** | ✅ VERIFIED |
| **Test Mode?** | ✅ Fully supported |
| **Our Usage** | Create orders for retry payment opportunities |
| **Required Params** | `amount` (integer, paise), `currency` (string, e.g. `"INR"`) |
| **Optional Params** | `receipt` (string, max 40 chars, **must be unique**), `notes` (object, max 15 pairs), `partial_payment` (boolean), `first_payment_min_amount` (integer) |
| **Order Statuses** | `created` → `attempted` → `paid` (3-state ONLY; no `expired`/`cancelled`) |
| **Error Behavior** | Duplicate `receipt` → `400 Bad Request` (NOT idempotent replay) |
| **Idempotency** | **NO idempotency header**. `receipt` uniqueness throws error on duplicate, does NOT return existing order |
| **Key Response Fields** | `id` (`order_xxx`), `entity`, `amount`, `amount_paid`, `amount_due`, `currency`, `receipt`, `status`, `attempts`, `notes`, `created_at` |

### 1.6 Create Payment Link

| Field | Value |
|-------|-------|
| **Endpoint** | `POST https://api.razorpay.com/v1/payment_links` |
| **Official Source** | https://razorpay.com/docs/api/payment-links/ |
| **Verified?** | ✅ VERIFIED |
| **Test Mode?** | ✅ Supported — **hard limit: 30 links per business in test mode** |
| **Our Usage** | Primary recovery action for RETRY and NEW_PAYMENT_LINK |
| **Required Params** | `amount` (integer, paise), `currency` (string) |
| **Optional Params** | `description`, `customer` ({name, contact, email}), `notify` ({sms, email, whatsapp}), `reminder_enable` (boolean), `expire_by` (Unix ts, **≥ 15 min in future**), `reference_id` (**unique, throws 400 on duplicate**), `accept_partial`, `notes`, `callback_url`, `callback_method` (**must be `"get"`**) |
| **Link Statuses** | `created`, `partially_paid`, `paid`, `cancelled`, `expired` |
| **Error Behavior** | Duplicate `reference_id` → `400 Bad Request` |
| **Idempotency** | **NO idempotency header**. Dedup via unique `reference_id` (app-level) |
| **Key Response Fields** | `id` (`plink_xxx`), `short_url`, `status`, `amount`, `amount_paid`, `reference_id`, `created_at` |

### 1.7 Invoice API

| Field | Value |
|-------|-------|
| **Endpoints** | `POST /v1/invoices`, `GET /v1/invoices/:id`, `POST /v1/invoices/:id/issue`, `PATCH /v1/invoices/:id`, `POST /v1/invoices/:id/cancel`, `POST /v1/invoices/:id/notify_by/:medium` |
| **Official Source** | https://razorpay.com/docs/api/invoices/ |
| **Verified?** | ✅ VERIFIED |
| **Test Mode?** | ✅ Supported |
| **Our Usage** | **TERTIARY** — overdue receivables. MVP uses synthetic events; real integration deferred |
| **Invoice Statuses** | `draft`, `issued`, `partially_paid`, `paid`, `cancelled`, `expired`, `deleted` |
| **Required Params** | `type` (`"invoice"`), `customer` (name required), `line_items` (array, 1-50 items) |
| **Idempotency** | No idempotency header. Use unique `receipt` field (max 40 chars) |

### 1.8 Capture Payment

| Field | Value |
|-------|-------|
| **Endpoint** | `POST https://api.razorpay.com/v1/payments/:id/capture` |
| **Official Source** | https://razorpay.com/docs/api/payments/ |
| **Verified?** | ✅ VERIFIED |
| **Required Params** | `amount` (integer, paise), `currency` (string) |
| **Our Usage** | Only if using manual capture flow. Prefer auto-capture. |

---

## 2. Webhook Events

| Event Name | Verified? | Source | Our Usage |
|------------|-----------|--------|-----------|
| `payment.failed` | ✅ | https://razorpay.com/docs/webhooks/events/ | Primary trigger: create FAILED_PAYMENT case |
| `payment.captured` | ✅ | Same | Confirm recovery success |
| `payment.authorized` | ✅ | Same | Intermediate state tracking |
| `order.paid` | ✅ | Same | Confirm order-level recovery |
| `payment_link.paid` | ✅ | Same | Confirm payment link recovery |
| `payment_link.expired` | ✅ | Same | Mark payment link action as failed |
| `payment_link.cancelled` | ✅ | Same | Handle cancelled link |
| `payment_link.partially_paid` | ✅ | Same | Track partial payment |
| `invoice.paid` | ✅ | Same | Confirm invoice recovery |
| `invoice.partially_paid` | ✅ | Same | Track partial invoice payment |
| `invoice.expired` | ✅ | Same | Handle invoice expiry |

> **IMPORTANT**: Event name is `payment_link.paid` (underscore), NOT `paymentlink.paid`.

### 2.1 Webhook Payload Structure

Verified from https://razorpay.com/docs/webhooks/validate-test/:

```json
{
  "entity": "event",
  "account_id": "acc_BFQ7uQEaa7j2z7",
  "event": "order.paid",
  "contains": ["payment", "order"],
  "payload": {
    "payment": { "entity": { "id": "pay_xxx", ... } },
    "order": { "entity": { "id": "order_xxx", ... } }
  },
  "created_at": 1691735748
}
```

**CRITICAL**: The JSON body does NOT contain an `id` or `event_id` field at root level.

### 2.2 Signature Verification

| Property | Value | Source |
|----------|-------|--------|
| Header | `X-Razorpay-Signature` | https://razorpay.com/docs/webhooks/validate-test/ |
| Algorithm | HMAC-SHA256 | Same |
| Key | Webhook Secret (Razorpay Dashboard) | Same |
| Message | Raw request body (unparsed bytes) | Same |
| Digest format | Hexadecimal string | Same |
| Comparison | Timing-safe / constant-time | Same |
| **Verified?** | ✅ VERIFIED | |

### 2.3 Event Deduplication

| Property | Value | Source |
|----------|-------|--------|
| Header | `X-Razorpay-Event-Id` | https://razorpay.com/docs/webhooks/validate-test/ |
| Location | HTTP header ONLY (not in JSON body) | Same |
| **Verified?** | ✅ VERIFIED | |

### 2.4 Delivery Semantics

| Property | Value | Source |
|----------|-------|--------|
| Delivery guarantee | At-least-once (duplicates possible) | https://razorpay.com/docs/webhooks/ |
| Response timeout | 5 seconds | Same |
| Retry policy | Exponential backoff over 24 hours | Same |
| Auto-disable | After 24h continuous failure | Same |
| **Verified?** | ✅ VERIFIED | |

---

## 3. Idempotency — Per-Operation

| Operation | Razorpay Idempotency Header | Our Mechanism |
|-----------|----------------------------|---------------|
| Create Order | ❌ None | App-level: generate deterministic `receipt` = `revpilot_case_{id}_retry_{n}`. Check locally before POST. Catch `400` as duplicate confirmation. |
| Create Payment Link | ❌ None | App-level: generate deterministic `reference_id` = `revpilot_case_{id}_link_{n}`. Check locally before POST. Catch `400` as duplicate confirmation. |
| Create Invoice | ❌ None | App-level: unique `receipt` per case. |
| Issue Refund | ✅ `X-Refund-Idempotency` (UUID v4, 10+ chars) | Use if refunds are needed. |
| Create Payout | ✅ `X-Payout-Idempotency` (mandatory, UUID v4, 4-36 chars) | Out of scope for MVP. |
| Direct Transfer | ✅ `X-Transfer-Idempotency` | Out of scope for MVP. |

**Source**: https://razorpay.com/docs/api/idempotency/

### Three-Layer Idempotency Architecture

| Layer | Mechanism | Implementation |
|-------|-----------|----------------|
| **A. Webhook Dedup** | `X-Razorpay-Event-Id` header | Store in `webhook_events` table with UNIQUE constraint. Return 200 immediately if duplicate. |
| **B. Internal Action Dedup** | Deterministic `action_idempotency_key` | `case_{id}_action_{type}_attempt_{n}`. Check `case_actions` before executing. Use DB transaction. |
| **C. External API Dedup** | Unique `receipt` / `reference_id` | Pre-check locally, then catch `400 Bad Request` as duplicate confirmation (not error). |

---

## 4. Rate Limits

| Property | Value | Source |
|----------|-------|--------|
| Documented limit | ~100 req/min per API key (approximate) | https://razorpay.com/docs/api/errors/ |
| HTTP code | `429 Too Many Requests` | Same |
| **Verified?** | ✅ VERIFIED (approximate; not exact) | |

### Implementation Config

```env
# Configuration-driven, not hardcoded
RAZORPAY_RATE_LIMIT_PER_MINUTE=100   # From docs (approximate)
RAZORPAY_TARGET_RATE_PER_MINUTE=80   # Conservative target with headroom
```

Both values configurable. If actual limit differs, only config changes.

**Backoff**: Exponential with jitter on 429. Max 3 retries. Circuit breaker after 5 consecutive failures.

---

## 5. Test Mode

| Capability | Supported? | Notes | Source |
|------------|-----------|-------|--------|
| Create Orders | ✅ | Full lifecycle | https://razorpay.com/docs/payments/payment-gateway/test-mode/ |
| Create Payment Links | ✅ | **Limit: 30 per business** | Same |
| Create Invoices | ✅ | Full lifecycle | Same |
| Webhook Delivery | ✅ | Must configure separately in Test Mode Dashboard | Same |
| Card Success Simulation | ✅ | Test cards + OTP ≥ 4 digits = success | Same |
| Card Failure Simulation | ✅ | OTP < 4 digits = failure | Same |
| UPI Success | ✅ | `success@razorpay` | Same |
| UPI Failure | ✅ | `failure@razorpay` | Same |
| SMS/WhatsApp/Email | ❌ | Suppressed in test mode | Same |
| Webhook Secret | Separate | Test mode has its own webhook secret | Same |

### Test Cards

| Network | Number | CVV | Expiry |
|---------|--------|-----|--------|
| Visa (Domestic) | `4111 1111 1111 1111` | Any 3 digits | Any future date |
| Mastercard (Domestic) | `5267 3181 8797 5449` | Any 3 digits | Any future date |
| RuPay | `6527 6589 0000 1005` | Any 3 digits | Any future date |
| Visa (International) | `4012 8888 8888 1881` | Any 3 digits | Any future date |

---

## 6. Payment Error Classification

### Verified Error Structure

```json
{
  "error": {
    "code": "BAD_REQUEST_ERROR",
    "description": "Payment failed due to insufficient funds",
    "source": "customer",
    "step": "payment_authentication",
    "reason": "insufficient_funds",
    "metadata": { "payment_id": "pay_xxx", "order_id": "order_xxx" }
  }
}
```

### Failure Category Mapping

| Razorpay `error_reason` | `error_source` | Our Category | Retry Probability | Source |
|------------------------|----------------|--------------|-------------------|--------|
| `expired_card` | `customer` | `HARD_DECLINE` | Near-zero | https://razorpay.com/docs/payments/payment-failure-reasons/ |
| `invalid_card_details` | `customer` | `HARD_DECLINE` | Zero | Same |
| `card_inactive` / `card_blocked` | `customer`/`gateway` | `HARD_DECLINE` | Near-zero | Same |
| `order_already_paid` | `business` | `HARD_DECLINE` | Zero (already paid) | Same |
| `insufficient_funds` | `customer` | `INSUFFICIENT_FUNDS` | Moderate (may resolve) | Same |
| `exceeded_limit` | `customer`/`gateway` | `SOFT_DECLINE` | Moderate | Same |
| `authentication_failed` / `invalid_otp` | `customer` | `SOFT_DECLINE` | Moderate (retry with correct OTP) | Same |
| `payment_timed_out` | `customer` | `TIMEOUT` | High (user didn't complete) | Same |
| `payment_cancelled` | `customer` | `CUSTOMER_CANCELLED` | Moderate (may return) | Same |
| `gateway_technical_error` / `GATEWAY_ERROR` | `gateway` | `GATEWAY_ERROR` | High (transient) | Same |
| `gateway_timed_out` | `gateway` | `TIMEOUT` | High (transient) | Same |
| `SERVER_ERROR` | `razorpay` | `SYSTEM_ERROR` | High (transient) | Same |
| `issuer_down` | `gateway` | `GATEWAY_ERROR` | High (bank maintenance) | Same |

> **Note**: This mapping is PROVISIONAL. Exact error reason strings will be validated with test-mode transactions and refined as needed. The probability column reflects general payment industry patterns, NOT measured Razorpay statistics.

---

## 7. Recovery Flow Design

### 7.1 Failed Payment → RETRY_PAYMENT_OPPORTUNITY

```
payment.failed webhook received
→ Verify X-Razorpay-Signature (HMAC-SHA256)
→ Check X-Razorpay-Event-Id for dedup
→ Store webhook event
→ Create/update FAILED_PAYMENT case
→ Decision Engine evaluates ENR for each action
→ If RETRY recommended and ENR > 0:
    → Create new Payment Link
       POST /v1/payment_links
       reference_id = "revpilot_case_{id}_attempt_{n}"
    → Status: WAITING_FOR_OUTCOME
→ Webhook: payment_link.paid → RECOVERED
→ Webhook: payment_link.expired → REASSESS
→ If all ENR ≤ 0 → STOP
```

### 7.2 Alternative: Order-based Retry

```
→ Create new Order
   POST /v1/orders
   receipt = "revpilot_case_{id}_retry_{n}"
→ Return order_id for frontend checkout
→ Webhook: order.paid → RECOVERED
→ Poll: GET /v1/orders/:id/payments for status
```

### 7.3 Abandoned Checkout

```
Application/synthetic event → checkout abandoned
→ Create ABANDONED_CHECKOUT case
→ If NEW_PAYMENT_LINK:
    → Create Payment Link for cart amount
→ If REMINDER:
    → Log intended communication (test mode: no real send)
```

### 7.4 Overdue Invoice

```
invoice.expired or synthetic event
→ Create OVERDUE_INVOICE case
→ If REMINDER:
    → POST /v1/invoices/:id/notify_by/email (if real invoice exists)
    → Or log intended reminder (synthetic)
→ If ESCALATE:
    → Log escalation record
```

---

## 8. Pagination

| API | Mechanism | Source |
|-----|-----------|--------|
| List Payments | `count` (max 100, default 10) + `skip` (offset) + `from`/`to` timestamps | https://razorpay.com/docs/api/payments/ |
| List Orders | `count` + `skip` | https://razorpay.com/docs/api/orders/ |
| List Payment Links | `count` + `skip` | https://razorpay.com/docs/api/payment-links/ |
| List Invoices | `count` + `skip` + `from`/`to` | https://razorpay.com/docs/api/invoices/ |

---

## 9. Items NOT Verified / NOT Used

| Item | Status | Decision |
|------|--------|----------|
| `POST /v1/payments` (server-side payment creation) | Does not exist | Payments created via Checkout/SDK only |
| `POST /v1/payments/:id/retry` | Does not exist | Use Payment Link or new Order |
| Subscription APIs | Not verified for this project | OUT OF SCOPE |
| Exact numeric rate limit | ~100/min (approximate) | Config-driven; backoff handles variance |
| Payment Link test-mode notifications | Suppressed | Log intended communications |
| Late authorization handling | Verified exists | Edge case; handle via `payment.authorized` webhook |
