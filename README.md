# RevPilot 

**RevPilot** is an autonomous revenue recovery agent designed to smartly recover failed payments, abandoned checkouts, and overdue invoices for Razorpay merchants.

Instead of generic "dumb retries", RevPilot operates on a strict deterministic **Economic Engine** that calculates the **Expected Net Revenue (ENR)** of every possible action (e.g., retrying a payment, sending a payment link, escalating to a human, or stopping entirely).

## Architecture

* **Backend**: FastAPI (Python)
* **Database**: SQLite (Local Fallback for MVP) / PostgreSQL (Production)
* **Agent Runtime**: Deterministic state machine (`OBSERVE` -> `PLAN` -> `POLICY` -> `ACT` -> `REASSESS`).
* **Frontend**: Vanilla HTML/JS/Tailwind Dashboard rendering real-time data from the API.
* **Integrations**: `httpx`-based Razorpay Adapter with HMAC-SHA256 webhook signature verification.

## Setup Instructions

1. **Clone the repository**
2. **Create a virtual environment**:
   ```bash
   cd backend
   python -m venv venv
   # Windows:
   .\venv\Scripts\Activate.ps1
   # Mac/Linux:
   source venv/bin/activate
   ```
3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Environment Variables**:
   Create a `.env` file in the `backend/` directory:
   ```env
   # Razorpay Test Mode Credentials
   RAZORPAY_KEY_ID=rzp_test_your_key_id
   RAZORPAY_KEY_SECRET=your_key_secret
   RAZORPAY_WEBHOOK_SECRET=your_webhook_secret
   ```

## Running the Application

### 1. Start the API & Background Worker
```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
*Note: The background worker (`AgentWorker`) will start automatically via the FastAPI lifespan hook to poll for eligible cases.*

### 2. Open the Merchant Console
Double click or open `demo/dashboard.html` in your web browser. 
(No Node.js/npm required for the MVP UI).

### 3. Run the Demo Setup
To see the system in action with a fresh database:
```bash
cd backend
python demo.py
```
This will clear the DB, inject a Positive EV case and a Negative EV case, and process them through the agent. Refresh the dashboard to see the results.

## Testing & Benchmarks

**Run the automated test suite** (Includes Adversarial, Webhook, and Failure tests):
```bash
cd backend
pytest test_failures.py test_adversarial.py test_api.py test_webhook.py test_economic_engine.py
```

**Run the Batch Evaluator (Benchmark)**:
Proves that RevPilot outperforms naive retry strategies on Net Recovered Revenue across 100 synthetic cases.
```bash
cd backend
python app/evaluation/batch_eval.py
```

## What is Real vs Simulated

* **REAL**: 
  * The deterministic economic engine (ENR calculations).
  * Webhook signature validation (HMAC-SHA256).
  * Webhook deduplication and transactional state transitions.
  * The autonomous agent polling loop.
* **SIMULATED**:
  * Success probabilities (`P=0.65`) are currently synthetic parameters. In production, these must be empirical historical metrics.
  * Without `.env` credentials, the Razorpay `httpx` adapter will gracefully simulate a failure (`401 Unauthorized`).
* **LIMITATIONS**:
  * SQLite is used instead of Postgres for immediate local testing.
  * The background worker is an `asyncio` loop rather than a distributed Celery/Kafka queue.
