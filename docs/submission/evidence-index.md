# Evidence Index

This index maps every major architectural claim in RevPilot directly to the source code that proves it. 

### PRODUCT
* **Claim:** The system evaluates candidate actions dynamically and calculates Expected Net Return.
* **File:** [`backend/app/economics/engine.py`](file:///C:/Users/abhay/OneDrive/Documents/Projects/RevPilot/backend/app/economics/engine.py)
* **Proof:** The `evaluate_case` function explicitly iterates through `available_actions`, passes each to `ml_predictor`, subtracts `cost` and `friction`, and sorts by `final_enr`.

### RAZORPAY
* **Claim:** RevPilot interacts with real Razorpay APIs for execution.
* **File:** [`backend/app/adapters/razorpay.py`](file:///C:/Users/abhay/OneDrive/Documents/Projects/RevPilot/backend/app/adapters/razorpay.py)
* **Proof:** The `RazorpayAdapter` contains `httpx.AsyncClient` logic implementing `POST /v1/payment_links`, including test-mode credentials and headers.

### ECONOMIC ENGINE
* **Claim:** The engine refuses to execute negative-ENR interventions (The Economic Stopping Layer).
* **File:** [`backend/app/agent/agent.py`](file:///C:/Users/abhay/OneDrive/Documents/Projects/RevPilot/backend/app/agent/agent.py)
* **Proof:** The `_process_case` loop intercepts the decision. If the best action is `NO_ACTION` or `final_enr < 0`, it transitions the case to `STOPPED` and aborts Razorpay execution.

### ML
* **Claim:** The ML model is a real LightGBM artifact with validated offline/online feature parity.
* **File:** [`backend/tests/test_ml_serving.py`](file:///C:/Users/abhay/OneDrive/Documents/Projects/RevPilot/backend/tests/test_ml_serving.py)
* **Proof:** The `test_feature_builder_parity` test loads the production `FeatureBuilder` and asserts `np.array_equal` against the actual `dataset.prepare_data` pipeline used during training.

### SECURITY
* **Claim:** Webhooks are cryptographically validated against `X-Razorpay-Signature`.
* **File:** [`backend/app/razorpay/webhooks.py`](file:///C:/Users/abhay/OneDrive/Documents/Projects/RevPilot/backend/app/razorpay/webhooks.py)
* **Proof:** The `WebhookVerifier.verify_signature` explicitly uses `hmac.new(secret, payload, hashlib.sha256).hexdigest()` before any database writes occur.

### RELIABILITY
* **Claim:** The system protects against duplicate webhooks and polling race conditions.
* **File:** [`backend/test_concurrency.py`](file:///C:/Users/abhay/OneDrive/Documents/Projects/RevPilot/backend/test_concurrency.py)
* **Proof:** Implements an `asyncio.gather` race condition test. Proves that PostgreSQL `FOR UPDATE SKIP LOCKED` guarantees only one worker can process a case or webhook concurrently.

### BENCHMARK
* **Claim:** RevPilot produces higher Net Recovered Revenue by avoiding wasteful interventions.
* **File:** [`docs/submission/benchmark-summary.md`](file:///C:/Users/abhay/OneDrive/Documents/Projects/RevPilot/docs/submission/benchmark-summary.md)
* **Proof:** The synthetic evaluation results show exactly how RevPilot beats `MAX_RETRY` across 5 random seed populations by intentionally lowering intervention volume.

### LIMITATIONS
* **Claim:** We do not hide our prototype constraints.
* **File:** [`README.md`](file:///C:/Users/abhay/OneDrive/Documents/Projects/RevPilot/README.md)
* **Proof:** The Limitations section explicitly declares our use of synthetic training data, Razorpay Test Mode bounds, and the `asyncio` polling architecture that would require Kafka for true production scale.
