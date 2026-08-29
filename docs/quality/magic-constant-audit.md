# Magic Constant & Literal Audit

Run Date: 2026-08-29

## Objective
Audit the entire repository for magic strings, hardcoded numbers, and implicit assumptions buried in the source code, and classify their removal or retention.

## Raw Findings & Classification

### 1. `app/agent/worker.py` & `main.py`
- **Found**: `poll_interval = 5`
- **Classification**: MOVED TO CONFIG
- **Action**: Extracted to `settings.WORKER_POLL_INTERVAL`.

### 2. `app/economics/engine.py`
- **Found**: `base_probs` dicts (`0.65`, `0.50`, etc.)
- **Found**: `costs`, `friction`, `risk` integers (e.g. `2.50`, `50.00`)
- **Found**: Decay multipliers (`0.25`, `0.05`)
- **Found**: Business rule `"INSUFFICIENT_FUNDS"` -> `0.8`
- **Classification**: MOVED TO DATA/POLICY
- **Action**: Completely removed from source code. Now consumed dynamically from `policy.json` via `policy_manager`.

### 3. `app/agent/memory.py`
- **Found**: `failure_reason="DECLINED_BY_BANK"` (mock string)
- **Classification**: BUG / REMOVE
- **Action**: Replaced with actual `getattr(case, "failure_reason", "unknown")`.

### 4. `app/models/domain.py`
- **Found**: `String(50)`, `String(255)`, `String(100)`
- **Classification**: MOVED TO CONFIG
- **Action**: Replaced with `settings.limits.ID_MAX_LENGTH`, `EMAIL_MAX_LENGTH`, `REFERENCE_MAX_LENGTH`, etc.

### 5. `app/api/endpoints.py`
- **Found**: `limit: int = Query(50, ge=1, le=100)`
- **Classification**: MOVED TO CONFIG
- **Action**: Replaced with `settings.pagination.DEFAULT_PAGE_SIZE` and `MAX_PAGE_SIZE`.
- **Found**: `recovery_rate = (recovered / total * 100)`
- **Classification**: IMMUTABLE TECHNICAL INVARIANT
- **Action**: Retained (Mathematical formula for percentage calculation).

### 6. `app/api/auth.py`
- **Found**: `JWT_SECRET_KEY = "test_secret_key_only"` (fallback)
- **Classification**: REMOVED
- **Action**: Triggers start-up failure via Pydantic Field validation unless testing explicitly passes it.
- **Found**: `ACCESS_TOKEN_EXPIRE_MINUTES = 30`
- **Classification**: MOVED TO CONFIG
- **Action**: Now pulled from `settings.security.JWT_EXPIRY_MINUTES`.

### 7. `app/razorpay/adapter.py`
- **Found**: `timeout=10.0`
- **Classification**: MOVED TO CONFIG
- **Action**: Replaced with `settings.razorpay.TIMEOUT_READ`.

### 8. `app/core/errors.py`
- **Found**: Various duplicated error string literals across the API.
- **Classification**: MOVED TO CONFIG/ENUM
- **Action**: Centralized into `ErrorCode` Enum taxonomy to ensure exact string matching and avoid magic exceptions.

### 9. `app/evaluation/batch_eval.py`
- **Found**: `[random.random() for _ in range(5)]`
- **Classification**: TEST FIXTURE
- **Action**: Retained (Mock synthetic world data for benchmarking purposes independent of agent).

## Summary
Zero business logic (such as economic value, attempt decay, action limits) is left hardcoded in the codebase. All operational bounds (like sizes and timeouts) have been successfully ported to `app.core.config`.
