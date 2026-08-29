# RevPilot Failure Matrix

This matrix maps system failures, edge cases, and API limits to RevPilot's handling mechanisms.

## 1. Webhook Failures

| Failure Class | Scenario | Handling Mechanism | Verification |
|---------------|----------|-------------------|--------------|
| **Replay Attack / Duplicate** | Razorpay retries the same event ID twice due to latency. | Event IDs are inserted into `webhook_events` with a `UNIQUE` constraint. Duplicates hit an `IntegrityError` and return `200 OK` (so Razorpay stops retrying). | **SYNTHETIC TESTED** (`test_webhook_deduplication`) |
| **Invalid Signature** | Attacker spoofs a webhook with arbitrary payload. | `X-Razorpay-Signature` is strictly verified using `hmac.compare_digest`. Invalid payloads return HTTP `400`. | **SYNTHETIC TESTED** (`test_webhook_invalid_signature`) |
| **Missing Event ID** | Payload lacks an `id` field. | Falls back safely; avoids DB unique constraint crash. Processes idempotent action updates. | **SYNTHETIC TESTED** (`test_webhook_missing_event_id`) |
| **Concurrent Webhooks** | Multiple threads hit the webhook endpoint simultaneously for the same action. | DB lock `with_for_update()` on `CaseAction` combined with status checks ensures amount is credited exactly once. | **SYNTHETIC TESTED** (`test_concurrency.py`) |
| **Genuine Payout Processing** | A real user makes a payment via an authentic Razorpay page. | Application exposes `/webhook/razorpay` over Ngrok and securely updates `RevenueRiskCase` and emits `AuditEvent` based on real `payment_link.paid` payloads. | **REAL TESTED** (See `real-razorpay-e2e-evidence.md`) |

## 2. Agent Execution Concurrency

| Failure Class | Scenario | Handling Mechanism | Verification |
|---------------|----------|-------------------|--------------|
| **Double Dispatch** | Multiple workers try to process the same `RevenueRiskCase`. | `AgentMemory.build_context` issues `SELECT FOR UPDATE`. The first worker transitions status to `ASSESSING`. Subsequent workers see status `!= OPEN` and abort. | **SYNTHETIC TESTED** (`test_concurrency.py`) |
| **Idempotency Leaks** | Razorpay link creation retry generates a different payload. | We use an MD5 hash of `case_id` + `action_type` + `attempt_count`. Retries emit the exact same idempotency key (<= 40 chars). | **REAL TESTED** (`test_real_razorpay_e2e` generates real links) |

## 3. Financial Integrity

| Failure Class | Scenario | Handling Mechanism | Verification |
|---------------|----------|-------------------|--------------|
| **Partial Payments** | User pays a smaller or larger amount than `amount_at_risk`. | The webhook explicitly sets `amount_recovered = amount_paid`. `get_dashboard_stats` purely sums `amount_recovered` for closed cases. | **REAL TESTED** (See `real-razorpay-e2e-evidence.md`) |
| **Float Truncation** | Policy configured with floats (`₹2.50`) instead of paise. | System strictly enforces integer paise using Pydantic `StrictInt`. Fails config on load rather than risking truncation. | **SYNTHETIC TESTED** (`test_policy_configuration.py`) |

## 4. API & Rate Limits

| Failure Class | Scenario | Handling Mechanism | Verification |
|---------------|----------|-------------------|--------------|
| **Razorpay API 429** | Agent hits rate limits. | Adapter surfaces failure. Agent marks action as `FAILED`. Backs off and retries on next execution loop up to `max_attempts`. | **SIMULATED** |
| **Razorpay API 400** | Malformed idempotency key or payload length violation. | Handled gracefully. Action recorded as `FAILED`. Execution loop terminates without crash. (e.g., >40 char id fix). | **TESTED** |
| **Database Lock Timeout** | Too many workers contending for the same `RevenueRiskCase`. | `with_for_update()` queues waiters. If Postgres `lock_timeout` hits, returns 500. Worker naturally retries next tick. | **SIMULATED** |
