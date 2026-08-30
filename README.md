# RevPilot
An autonomous revenue recovery engine that uses Machine Learning to maximize Expected Net Return (ENR) for Razorpay merchants.

## The Problem
Revenue at risk isn't the same as revenue worth chasing. RevPilot evaluates the next recovery intervention by both its chance of success and its economic cost—and knows when to stop.

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
If a **₹50,000** transaction fails for a loyal customer:
* ML predicts a 71.33% recovery probability for `CREATE_PAYMENT_LINK`.
* `(5,000,000 paise * 0.7133) - 250 paise (Cost) - 500 paise (Friction) = +3,565,731 paise ENR`.
* **Decision: Execute.**

If a **₹28** transaction fails (marginal value case):
* ML predicts a **73.59%** recovery probability for `CREATE_PAYMENT_LINK` (ENR: `2060 - 750 = +1310 paise`).
* ML predicts only a **56.08%** recovery probability for `SEND_REMINDER` (ENR: `1570 - 250 = +1320 paise`).
* **Decision: SEND_REMINDER.** RevPilot intelligently down-selects to a lower-probability, cheaper intervention because the net economic yield is higher.

## Benchmark 
*(Tested on 5 independent synthetic seed populations of 100 cases)*

Across all seeds, RevPilot mathematically outperformed a `MAX_RETRY` strategy on **Net Recovered Revenue (INR)**. It accomplished this by reducing unnecessary interventions by ~15%, refusing to throw good money after bad.
*(See `docs/submission/benchmark-summary.md` for exact metrics).*

## Security & Reliability
Built for enterprise stability:
* **PostgreSQL Concurrency:** `FOR UPDATE SKIP LOCKED` guarantees webhook deduplication and prevents polling race conditions.
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
