# RevPilot
An autonomous revenue recovery engine that uses Machine Learning to maximize Expected Net Return (ENR) for Razorpay merchants.

## The Problem
Revenue isn\'t worth recovering at any cost. 

Revenue at risk isn\'t the same as revenue worth chasing. RevPilot evaluates the next recovery intervention by both its chance of success and its economic cost—and knows when to stop.

## What RevPilot Does
RevPilot operates as an asynchronous, post-abandonment recovery agent. When a payment fails:
1. **Context + Candidate Action:** The system feeds the customer context and potential interventions to our ML predictor.
2. **ML Recovery Probability:** A LightGBM model calculates the precise probability of recovery *conditioned on that specific action* (e.g. 71.3% for a Payment Link vs 58.1% for a Silent Retry).
3. **Economic Value:** The Economic Engine maps this probability against the transaction amount and subtracts the exact cost and friction of the intervention.
4. **Policy Gate:** If the Expected Net Return (ENR) is negative, the system halts. If positive, the intervention is approved.
5. **Bounded Execution:** RevPilot securely calls the Razorpay API to execute the intervention (e.g., creating a Payment Link) and listens for the verified HMAC-SHA256 webhook to close the case.

## Why This Is Different
RevPilot focuses on the economic decision layer for post-failure asynchronous recovery.
* **Not a naive retry loop:** We explicitly evaluate whether the *next* intervention is economically justified before spending merchant capital.
* **Not an LLM chatbot:** We intentionally exclude generative AI from the execution path. Financial execution requires deterministic, causally-structured models (LightGBM) bounded by strict economic logic.
* **Not synchronous checkout routing (Optimizer):** Unlike Razorpay Optimizer (which routes payments during checkout to prevent failures), RevPilot handles the asynchronous human recovery layer *after* the terminal failure.
* **Not just workflow automation (Agent Studio):** While Agent Studio can execute recovery steps, RevPilot provides the *economic stopping layer*—the mathematical brain that decides if a step is actually worth taking.

## Real Razorpay Proof
This prototype was built with real engineering constraints. We implemented and tested against **Razorpay Test Mode**:
* **Real Payment Links:** Uses the `httpx` adapter to hit `POST /v1/payment_links`.
* **Real Webhook Delivery:** Fully parses and deduplicates real Razorpay `payment_link.paid` payloads.
* **HMAC Validation:** Cryptographically verifies the `X-Razorpay-Signature`.
* **Financial Integrity:** Handles partial payments and prevents overpayment ceilings.

## Machine Learning
* **Model:** LightGBM
* **Prediction:** $P(\text{recovery by horizon} \mid \text{context, candidate action})$
* **Data (Synthetic):** *RevPilot uses a real LightGBM recovery-probability model trained and evaluated on a causally structured synthetic world model. Razorpay Test Mode is used for live payment execution and webhook validation.* 

## The Economic Decision

RevPilot estimates the value of each recovery intervention and decides whether the next action is economically justified. The core operating principle is that **HIGHER PROBABILITY != HIGHER ECONOMIC VALUE**.

### 🌟 The Hero Case: Marginal Value (₹28)
A ₹28 payment fails. RevPilot evaluates the top two candidate actions:

**Action 1: CREATE_PAYMENT_LINK**
* **Probability:** 73.593%
* **Expected Value:** 2,060 paise int(2800 * 0.73593)
* **Cost:** 250 paise
* **Friction:** 500 paise
* **Risk:** 0 paise
* **ENR:** +1,310 paise

**Action 2: SEND_REMINDER**
* **Probability:** 56.084%
* **Expected Value:** 1,570 paise int(2800 * 0.56084)
* **Cost:** 50 paise
* **Friction:** 200 paise
* **Risk:** 0 paise
* **ENR:** +1,320 paise

**Selected Action:** SEND_REMINDER. RevPilot intelligently down-selects to a lower-probability, cheaper intervention because the net economic yield is higher.

### Other Scenarios

**CASE A: High Value (₹50,000) — Execute High-Friction Action**
* ML predicts a **71.329%** recovery probability for CREATE_PAYMENT_LINK.
* ENR Calculation: int(5,000,000 * 0.71329) - 250 (Cost) - 500 (Friction) = +3,565,731 paise ENR.
* **Decision:** CREATE_PAYMENT_LINK. The high expected value easily absorbs the friction.

**CASE C: Negative Yield (₹5) — Hard Stop**
* ML predicts a **71.145%** recovery probability for CREATE_PAYMENT_LINK.
* ENR Calculation: int(500 * 0.71145) - 250 (Cost) - 500 (Friction) = -395 paise ENR.
* Even the cheapest action (SEND_REMINDER) yields a negative ENR (-34 paise).
* **Decision:** NO_ACTION (STOP). RevPilot knows when the economically correct recovery action is no action.

## Benchmark 
*(Tested on 5 independent synthetic seed populations of 100 cases)*

Across all seeds, RevPilot mathematically outperformed a `MAX_RETRY` strategy on **Net Recovered Revenue (INR)**. It accomplished this by reducing unnecessary interventions by ~15%, refusing to throw good money after bad.
*(See `docs/submission/benchmark-summary.md` for exact metrics).*

## Security & Reliability
Built for enterprise stability:
* **PostgreSQL Concurrency:** `FOR UPDATE SKIP LOCKED` enforces webhook deduplication and prevents polling race conditions.
* **Strict State Machine:** Adheres to deterministic `OPEN -> ASSESSING -> EXECUTING -> WAITING_FOR_OUTCOME -> RECOVERED` transitions.
* **Feature Schema Validation:** The ML Predictor will refuse to load if the runtime `metadata.json` schema version mismatches the trained artifact (`MODEL_SCHEMA_MISMATCH`).

## Architecture
```mermaid
graph TD
    A[Razorpay Webhook / Failure] --> B[RevPilot Postgres DB]
    B --> C[Agent Worker Polling]
    C --> D[ML Predictor]
    D -->|P(Recovery\|Action)| E[Economic Engine]
    E -->|Expected Net Return| F[Policy Manager]
    F -->|Approved Action| G[Razorpay Adapter]
    G --> H[Create Payment Link / Retry]
```

## 60-Second Demo

**1. Setup Environment**
```bash
cd backend
python -m venv venv
source venv/bin/activate # or .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**2. Setup Database & Demo Cases**
```bash
# This clears the local DB and injects two deterministic test cases
python demo.py
```

**3. Run the Economic Engine Evaluation**
```bash
# Watch the ML model and Economic Engine calculate probabilities and ENR side-by-side
python scripts/run_live_case.py
```

## Engineering Decisions & Tradeoffs

We engineered RevPilot under the constraint that financial execution requires extreme determinism and verifiability.

* **Why deterministic logic surrounds ML:** ML is excellent at guessing probabilities but terrible at strict accounting rules. By isolating the LightGBM model so it *only* emits probabilities, we ensure the Economic Engine and Policy Manager have final, mathematical veto power over execution.
* **Why LLMs were excluded from execution:** Generative AI suffers from hallucinations and non-determinism. While LLMs are great for generating email copy, putting them in the critical path of routing funds or calculating costs is an unacceptable compliance risk. 
* **Why LightGBM over Deep Learning:** We tested neural architectures, but tabular financial data with categorical features (merchant type, action type) strongly favors gradient boosting. LightGBM provided significantly faster inference and explicit feature importance (SHAP) for auditability.
* **Why PostgreSQL locking matters:** Webhooks can be delivered out of order or duplicated. We intentionally rely on explicit SELECT ... FOR UPDATE SKIP LOCKED transaction bounds and deterministic state machines (OPEN -> ASSESSING -> EXECUTING) to ensure idempotent execution. 
* **Why synthetic data:** We do not possess proprietary Razorpay merchant datasets. To rigorously prove the architecture, we built a causally-structured world model to generate synthetic telemetry.
* **What failed during development:** We initially attempted to compute Expected Net Return (ENR) *inside* the ML model (predicting direct monetary yield). This failed because it conflated merchant policy changes (cost of SMS) with customer behavior changes. We had to architecturally split (recovery)$ from (economic)$.
* **What we intentionally did not build:** We did not build a generic workflow builder. Razorpay Agent Studio already solves workflow generation. We built the *economic stopping rule* missing from those workflows.

## Limitations
* **Synthetic Training Data:** Because we do not have access to proprietary Razorpay merchant historical data, the LightGBM model is trained on a mathematically rigorous synthetic dataset. In production, it must be retrained on real historical telemetry.
* **Test Mode Only:** The Razorpay credentials operate strictly in Test Mode.
* **Polling Architecture:** The background worker uses `asyncio` polling. Production scale would require Kafka/SQS event triggers.

## Repository Entry Points
* [Demo Script & Pitch](docs/submission/demo-script.md)
* [Judge's Guide (Evidence Map)](JUDGES_GUIDE.md)
* [ML Integration Verification](docs/ml/integration-verification.md)
* [Differentiation](docs/submission/differentiation.md)
* [Benchmark Summary](docs/submission/benchmark-summary.md)
