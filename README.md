# RevPilot: Economic Decision Engine for Revenue Recovery

## Core Thesis
> **Revenue at risk isn't the same as revenue worth chasing.**

RevPilot is an autonomous economic decision engine for post-abandonment payment recovery. It evaluates every failed payment to determine the exact expected net return (ENR) of intervention. 

RevPilot is not an "AI payment recovery" tool or a naive "AI-powered retry system." It is a mathematical governor that stops recovery workflows when they become unprofitable, and globally optimizes recovery capital when budgets are constrained.

---

## The Four-Layer Decision Stack

RevPilot breaks revenue recovery into four distinct economic decisions:

### 1. Case Economics
**"Should I spend money recovering this payment?"**
* **Mechanism:** Action-conditioned ML recovery probability + Expected Net Return (ENR).
* **Execution:** Calculates the cost, friction, and risk of candidate actions and compares them to the expected value.

### 2. Portfolio Economics
**"Where should limited recovery budget be spent?"**
* **Mechanism:** Multiple-Choice Knapsack Problem (MCKP) dynamic programming.
* **Execution:** If a merchant limits their recovery budget, RevPilot globally optimizes interventions across a batch of cases to maximize total yield, actively downgrading or dropping cases to conserve capital.

### 3. Constraint Economics
**"What additional expected recovery would more budget unlock?"**
* **Mechanism:** Discrete Marginal Budget Value (Shadow Price).
* **Execution:** Calculates the exact objective delta `(Z(B + Δ) - Z(B)) / Δ` using actual optimizer objective values at a tested budget increment. It answers whether relaxing the budget is economically worthwhile.

### 4. Temporal Economics [RESEARCH / DEMO SIMULATION]
**"Should we act now, or is waiting economically better?"**
* **Mechanism:** Deterministic temporal decision simulation.
* **Execution:** Compares the ENR of immediate intervention against the expected value of waiting for synthetic organic recovery, penalized by delay risk. Demonstrates `ACT_NOW`, `DEFER`, or `STOP`. *(Note: This is a read-only research simulation, not a production execution feature).*

---

## Architectural Principle

> **ML predicts. Economics values. Policy controls. Executor acts.**

Financial execution requires extreme determinism and verifiability.
* **No LLMs in the execution path:** Generative AI is intentionally excluded from the critical financial execution path to prevent hallucination and preserve strict auditability.
* **Bounded ML:** The LightGBM model is not permitted to execute actions or calculate money. It *only* emits probabilities.
* **Mathematical Authority:** The deterministic Economic Engine and Policy Manager have final, hard-coded veto power over execution.

---

## The Economics in Action

### 🌟 Hero Example: The Marginal Value (INR 28)
An INR 28 payment fails. RevPilot evaluates the candidate actions:

**Action 1: CREATE_PAYMENT_LINK**
* **Probability:** ~73.6%
* **Cost & Friction:** 750 paise
* **Expected Net Return (ENR):** ≈ INR 13.10

**Action 2: SEND_REMINDER**
* **Probability:** ~56.1%
* **Cost & Friction:** 250 paise
* **Expected Net Return (ENR):** ≈ INR 13.20

**Result:** The lower-probability action wins economically. RevPilot intelligently down-selects to a cheaper intervention because the net economic yield is higher.

### 🛑 Stop Example: The Negative Yield (INR 5)
An INR 5 payment fails. 
* ML predicts a highly confident **~71.1%** recovery probability for a Payment Link.
* Expected Value = INR 3.55
* Cost & Friction = INR 7.50
* **ENR = -INR 3.95 (Negative)**

**Result:** `NO_ACTION`. Even the cheapest action yields a negative ENR. RevPilot proves it knows when the economically correct recovery action is to do nothing.

---

## Real vs. Synthetic Evidence

RevPilot establishes strict boundaries between real engineering integration and synthetic assumptions required for demonstration without proprietary data.

### REAL TESTED (Production Infrastructure)
* **Razorpay Test Mode Integration:** Executes real payment links via HTTP adapters.
* **Webhook Processing:** Fully parses, verifies (HMAC-SHA256), and deduplicates real `payment_link.paid` payloads.
* **Persistence & State:** Strict `OPEN -> ASSESSING -> EXECUTING` PostgreSQL state machine with `FOR UPDATE SKIP LOCKED` concurrency protection.
* **Accounting:** Handles partial payments and enforces overpayment ceilings.

### SYNTHETIC TESTED (Demo Assumptions)
* **ML Model:** Trained on a causally-structured synthetic world model.
* **Temporal Organic Recovery:** The organic decay curves in the Temporal Deferral simulator are synthetic research assumptions.
* **Portfolio Inputs:** The case batches fed into the MCKP optimizer benchmark are synthetically generated.

*(Do not interpret synthetic recovered revenue in benchmarks as real-world recovered revenue).*

---

## Model Selection Trade-Offs

We evaluated multiple architectures, including deep neural networks. **LightGBM** was selected based on objective evidence for this specific tabular financial domain:
* **Predictive Value:** Gradient boosting natively handles categorical features (merchant type, action type) and missing data better than simple MLPs.
* **Complexity Trade-Offs:** Provides significantly faster CPU inference (critical for high-throughput webhook processing) and explicit feature importance (SHAP) for auditability.
* **No "Magic" Claims:** The model is not claimed to be "perfect" or "zero-leakage" in production; it requires retraining on real merchant data. It serves as a rigorously integrated proof-of-concept.

---

## Security & Reliability Controls

The implementation includes the following enforced controls:
* **Authorization / RBAC:** API endpoints enforce role-based access control (e.g., preventing cross-merchant IDOR).
* **Webhook Signature Validation:** Rejects payloads failing cryptographic HMAC verification.
* **Idempotency & Concurrency:** Database transaction handling prevents double-execution and polling race conditions.
* **State Validation:** Reject transitions outside the strict recovery state machine.

---

## Test Status

The system is validated by a comprehensive suite covering economics, portfolio optimization, temporal simulation, ML boundaries, and adversarial security.

**Final Test Run Results:**
* **Passed:** 73
* **Skipped:** 1 *(test_e2e_razorpay.py requires live Razorpay network credentials)*
* **Failed:** 0

---

## Quick Start & Demos

**1. Setup Environment**
```bash
cd backend
python -m venv venv
source venv/bin/activate # or .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**2. Demo: Live Case Execution**
Watch the ML model and Economic Engine calculate probabilities and ENR side-by-side.
```bash
python scripts/run_live_case.py
```

**3. Demo: Portfolio Optimizer & Shadow Price**
Watch the MCKP engine downgrade interventions to respect budget constraints, and calculate the Shadow Price.
```bash
python scripts/run_portfolio.py
```

**4. Demo: Temporal Deferral Simulation**
Watch the temporal economic simulator evaluate `ACT_NOW` vs `DEFER` across time.
```bash
python scripts/run_temporal.py
```

**5. Run the Test Suite**
```bash
pytest -v
```

---
*Developed for the Razorpay AI Hackathon 2026.*
