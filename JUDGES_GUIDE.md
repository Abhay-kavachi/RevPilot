# RevPilot Judge's Guide

This guide maps common Razorpay evaluator questions directly to the verifiable evidence in the repository. We designed RevPilot with strict architectural boundaries—if you want to see how we solved a specific engineering challenge, start here.

| Evaluator Question | Architectural Evidence | Target File / Location |
| :--- | :--- | :--- |
| **Real Razorpay API Integration** | Idempotent HTTPX adapter creating real Payment Links and handling Test Mode failures. | [`backend/app/adapters/razorpay.py`](file:///C:/Users/abhay/OneDrive/Documents/Projects/RevPilot/backend/app/adapters/razorpay.py) |
| **Webhook Security & Deduplication** | HMAC-SHA256 signature validation and idempotent processing of `payment_link.paid` events. | [`backend/app/api/webhooks.py`](file:///C:/Users/abhay/OneDrive/Documents/Projects/RevPilot/backend/app/api/webhooks.py) |
| **Concurrency & Race Conditions** | PostgreSQL `FOR UPDATE SKIP LOCKED` implementation preventing duplicate webhook/polling state corruptions. | [`backend/test_concurrency.py`](file:///C:/Users/abhay/OneDrive/Documents/Projects/RevPilot/backend/test_concurrency.py) |
| **Financial Accounting Rules** | Strict handling of integer paise, partial payments, and overpayment ceilings during recovery. | [`backend/test_accounting.py`](file:///C:/Users/abhay/OneDrive/Documents/Projects/RevPilot/backend/test_accounting.py) |
| **ML Serving Correctness** | Strict feature schema versioning, dataset provenance, and offline/online exact vector parity tests. | [`backend/tests/test_ml_serving.py`](file:///C:/Users/abhay/OneDrive/Documents/Projects/RevPilot/backend/tests/test_ml_serving.py) |
| **ML Causal Evidence** | Documentation proving the action-conditioned LightGBM differentiates interventions based on context. | [`docs/ml/integration-verification.md`](file:///C:/Users/abhay/OneDrive/Documents/Projects/RevPilot/docs/ml/integration-verification.md) |
| **Economic Decision Logic** | The engine that mathematically maps `P(recovery) * Amount` against Action Costs and Frictions. | [`backend/app/economics/engine.py`](file:///C:/Users/abhay/OneDrive/Documents/Projects/RevPilot/backend/app/economics/engine.py) |
| **Policy Enforcement** | Externalized configuration decoupling financial rules from core code. | [`backend/policy.json`](file:///C:/Users/abhay/OneDrive/Documents/Projects/RevPilot/backend/policy.json) |

### Note on Verification
If you run `pytest .` in the `backend/` directory, the architectural boundaries are verified automatically (58 tests passed; 1 Razorpay external-integration test skipped because the Test Mode environment limit was reached). 
