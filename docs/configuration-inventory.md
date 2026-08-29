# Configuration Inventory

All technical configurations for RevPilot are centralized in `app.core.config.py` using `pydantic-settings`, reading from `.env`. Business rules live in `policy.json`.

## 1. Security Configuration (`SecurityConfig`)

| NAME | TYPE | DEFAULT | SOURCE | PURPOSE | SECURITY SENSITIVITY | REQUIRES RESTART? |
|---|---|---|---|---|---|---|
| `JWT_SECRET_KEY` | `str` | NONE | `.env` | Signs JWTs | HIGH | YES |
| `JWT_EXPIRY_MINUTES` | `int` | `30` | `.env` | Auth session lifespan | MEDIUM | YES |
| `ALGORITHM` | `str` | `"HS256"` | Code | Token hashing | HIGH | YES |

## 2. Limits & Constraints (`LimitsConfig`)

| NAME | TYPE | DEFAULT | SOURCE | PURPOSE | SECURITY SENSITIVITY | REQUIRES RESTART? |
|---|---|---|---|---|---|---|
| `ID_MAX_LENGTH` | `int` | `50` | `LIMITS_` | Bound DB varchar length | LOW | YES (Schema) |
| `EMAIL_MAX_LENGTH` | `int` | `255` | `LIMITS_` | Bound DB varchar length | LOW | YES (Schema) |
| `WEBHOOK_MAX_BYTES` | `int` | `5242880`| `LIMITS_` | Memory exhaustion protection | HIGH | YES |

## 3. Pagination Configuration (`PaginationConfig`)

| NAME | TYPE | DEFAULT | SOURCE | PURPOSE | SECURITY SENSITIVITY | REQUIRES RESTART? |
|---|---|---|---|---|---|---|
| `DEFAULT_PAGE_SIZE` | `int` | `50` | `PAGINATION_` | API Default response len | LOW | NO (Live config possible) |
| `MAX_PAGE_SIZE` | `int` | `100` | `PAGINATION_` | API Protection | LOW | YES |

## 4. Razorpay Configuration (`RazorpayConfig`)

| NAME | TYPE | DEFAULT | SOURCE | PURPOSE | SECURITY SENSITIVITY | REQUIRES RESTART? |
|---|---|---|---|---|---|---|
| `KEY_ID` | `str` | NONE | `RAZORPAY_` | API Auth | HIGH | YES |
| `KEY_SECRET` | `str` | NONE | `RAZORPAY_` | API Auth | HIGH | YES |
| `WEBHOOK_SECRET` | `str` | NONE | `RAZORPAY_` | Payload signing | HIGH | YES |
| `TIMEOUT_READ` | `int` | `15` | `RAZORPAY_` | Network resilience | LOW | YES |

## 5. Economic & Recovery Policy (`policy.json`)

**Source:** `policy.json` (Consumed by `policy_manager`)
**Who Can Change It:** Risk/Operations Team
**Requires Restart:** No, can be reloaded on the fly (singleton rebuild).
**Auditable:** Yes, JSON format can be versioned in Git.
**Test Override:** Yes, `PolicyManager(policy_path=...)` allows full mock testing.

| BLOCK | PURPOSE |
|---|---|
| `economic_policy.base_probabilities` | Base success likelihood for actions (e.g. `CREATE_PAYMENT_LINK` -> `0.65`). |
| `economic_policy.failure_reason_multipliers`| Modifier based on webhook failure code. |
| `economic_policy.attempt_adjustments` | Step-wise modifier based on attempt count. |
| `economic_policy.age_adjustments` | Step-wise modifier based on case age. |
| `economic_policy.action_costs` | Explicit cost per action in currency subunit. |
| `recovery_policy.max_attempts` | The total number of allowed actions before giving up. |
| `recovery_policy.stop_threshold` | EV limit to stop processing entirely. |
