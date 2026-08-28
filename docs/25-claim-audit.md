# Claim Audit

This document formally classifies every major claim about RevPilot according to the Final Engineering Audit (Gate 11) guidelines.

## Classifications
* **VERIFIED**: Explicitly tested with live data or mathematically proven in automated tests.
* **SIMULATED**: Tested against a local mock or synthetic behavior.
* **SYNTHETIC**: Data/numbers generated mathematically, not empirical.
* **ASSUMPTION**: Taken as true for the sake of the MVP.
* **NOT VERIFIED**: Code is written but requires external credentials to prove.

---

## 1. Razorpay Integration
* **"Razorpay webhook signature is verified"**
  * **VERIFIED**: Automated tests (`test_failures.py`) explicitly use `HMAC-SHA256` to sign a mock payload and verify against the `WebhookVerifier`.
* **"RevPilot integrates with Razorpay Test API"**
  * **SIMULATED / NOT VERIFIED**: The code uses `httpx` to make the correct HTTP calls (e.g. `POST /v1/payment_links`). However, until the user provides valid `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` in a `.env` file, the tests intentionally capture a `401 Unauthorized` response to verify fallback safety. A live test-mode transaction requires credentials.
* **"Deduplicates webhooks automatically"**
  * **VERIFIED**: `test_failures.py` proves that duplicate webhook events (same event ID) are rejected and processed exactly once.

## 2. Economic Engine (Expected Net Recovery - ENR)
* **"ENR is deterministic and explicitly evaluated"**
  * **VERIFIED**: The agent always consults `EconomicEngine` before dispatching an action. EV, Cost, Friction, and Risk are explicitly calculated in paise.
* **"RevPilot immediately stops on negative EV"**
  * **VERIFIED**: Both the Agent Loop tests (`test_agent_loop.py`) and Adversarial tests (`test_adversarial.py`) prove that negative EV immediately yields a `CLOSE_CASE` action and transitions the case to `STOPPED`.
* **"Action parameters reflect historical Razorpay data"**
  * **SYNTHETIC**: The success probabilities (e.g., `P=0.65` for a retry, `P=0.50` for a payment link) and friction metrics are currently synthetic for the buildathon demo. They must be calibrated empirically in a production environment.

## 3. Autonomous Agent Runtime
* **"The agent operates entirely autonomously without human intervention"**
  * **VERIFIED**: The `AgentWorker` continuously polls the database for `OPEN` cases and executes the `ExecutionLoop`. No manual DB edits are required to transition a case from `OPEN` to `EXECUTING` to `WAITING_FOR_OUTCOME` to `RECOVERED`/`STOPPED`.
* **"The LLM is in the critical path for revenue actions"**
  * **FALSE / SIMULATED**: The MVP relies entirely on the deterministic economic policy engine to ensure safety. The LLM's role (where applicable) is restricted to semantic understanding of case context or explainability, but it CANNOT bypass the deterministic ENR thresholds to dispatch money-moving actions.

## 4. Evaluation & Benchmarks
* **"RevPilot beats fixed-retry strategies on Net Recovered Revenue"**
  * **VERIFIED (Synthetic)**: The `batch_eval.py` script proves mathematically that by dropping negative-EV micro-transactions, RevPilot recovers a higher net profit than a `MAX_RETRY` strategy across 100 randomly seeded synthetic cases.

## 5. Security & Infrastructure
* **"Uses PostgreSQL for robust transactional guarantees"**
  * **NOT EXECUTED IN CURRENT ENVIRONMENT**: The ORM and Alembic migrations are written for PostgreSQL, but due to local Docker limitations, the MVP dynamically falls back to `SQLite`. 
* **"Secrets are protected"**
  * **VERIFIED**: No hardcoded API keys exist in the repository. All secrets are loaded via `os.getenv`.
