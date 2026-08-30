# RevPilot
An autonomous revenue recovery engine that uses Machine Learning to maximize Expected Net Return (ENR) for Razorpay merchants.

## The Problem
Every payment gateway offers retries, but generic retries have a fatal flaw: they optimize for gross conversion while ignoring the cost of recovery. They will happily spend ₹50 in SMS fees and brand friction to chase a ₹100 payment that the customer was never going to complete. 

**Revenue at risk is not the same as revenue worth chasing.**

## What RevPilot Does
RevPilot operates as an asynchronous, post-abandonment recovery agent. When a payment fails:
1. **Context + Candidate Action:** The system feeds the customer context and potential interventions to our ML predictor.
2. **ML Recovery Probability:** A LightGBM model calculates the precise probability of recovery *conditioned on that specific action* (e.g. 63% for a Payment Link vs 50% for a Silent Retry).
3. **Economic Value:** The Economic Engine maps this probability against the transaction amount and subtracts the exact cost and friction of the intervention.
4. **Policy Gate:** If the Expected Net Return (ENR) is negative, the system halts. If positive, the intervention is approved.
5. **Bounded Execution:** RevPilot securely calls the Razorpay API to execute the intervention (e.g., creating a Payment Link) and listens for the verified HMAC-SHA256 webhook to close the case.

## Why This Is Different
* **Not a naive retry loop:** We explicitly evaluate whether the *next* intervention is economically justified before spending merchant capital.
* **Not an LLM chatbot:** We intentionally exclude generative AI from the execution path. Financial execution requires deterministic, causally-structured models (LightGBM) bounded by strict economic logic.
* **Not synchronous checkout routing:** Unlike Razorpay Optimizer (which routes payments during checkout), RevPilot handles the asynchronous human recovery layer hours or days after the terminal failure.

## Real Razorpay Proof
This prototype was built with real engineering constraints. We implemented and tested against **Razorpay Test Mode**:
* **Real Payment Links:** Uses the `httpx` adapter to hit `POST /v1/payment_links`.
* **Real Webhook Delivery:** Fully parses and deduplicates real Razorpay `payment_link.paid` payloads.
* **HMAC Validation:** Cryptographically verifies the `X-Razorpay-Signature`.
* **Financial Integrity:** Handles partial payments and prevents overpayment ceilings.

## Machine Learning
* **Model:** LightGBM
* **Prediction:** $P(\text{recovery by horizon} \mid \text{context, candidate action})$
* **Data (Synthetic):** *The production prototype uses a real ML model trained and evaluated on a causally structured synthetic dataset (100k chronological events). Razorpay Test Mode is used for live payment execution and webhook validation.* 

## The Economic Decision
If a **₹50,000** transaction fails for a loyal customer:
* ML predicts a 63% recovery probability for `CREATE_PAYMENT_LINK`.
* `(500,000 paise * 0.63) - 250 paise (SMS cost) - 500 paise (Friction) = +317,316 paise ENR`.
* **Decision: Execute.**

If a **₹50** transaction fails for insufficient funds:
* ML predicts a 15% recovery probability.
* `(500 paise * 0.15) - 250 paise (SMS cost) - 500 paise (Friction) = -675 paise ENR`.
* **Decision: NO_ACTION (Halt).**

## Benchmark 
*(Tested on 5 independent synthetic seed populations of 100 cases)*

Across all seeds, RevPilot mathematically outperformed a `MAX_RETRY` strategy on **Net Recovered Revenue (INR)**. It accomplished this by reducing unnecessary interventions by ~15%, refusing to throw good money after bad.
*(See `docs/submission/benchmark-summary.md` for exact metrics).*

## Security & Reliability
Built for enterprise stability:
* **PostgreSQL Concurrency:** `FOR UPDATE SKIP LOCKED` guarantees webhook deduplication and prevents polling race conditions.
* **Strict State Machine:** Adheres to deterministic `OPEN -> IN_PROGRESS -> RECOVERED/FAILED` transitions.
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
