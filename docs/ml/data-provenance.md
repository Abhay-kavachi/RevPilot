# Data Provenance

## Primary Data Source: Synthetic Causal World Model
- **Source**: ackend/ml/world_model.py (Custom Data Generator)
- **Retrieval Date**: N/A (Generated Locally)
- **License**: N/A (Internal to RevPilot)
- **Purpose**: To provide a strictly causally-controlled sequence of payment failures, recovery actions, and potential outcomes.
- **Directly used in ML**: Yes (100% of Training, Validation, and Test data).
- **Public Data Usage**: None.

## Architectural Decision: Rejection of External Public Datasets
Under the project guidelines, we evaluated the use of external public datasets (e.g., open e-commerce or financial transaction repositories) to calibrate our behavioral distributions. 

However, we explicitly **rejected** external integration and elected to rely 100% on the synthetic generator for the following reasons:
1. **Causal Control**: Our primary evaluation metric is **Regret** (Oracle Utility - Strategy Utility). External datasets only record *observed* outcomes, making it impossible to independently verify the potential outcome of unchosen actions (e.g., what would have happened if an email was sent instead of a payment link). 
2. **Action-Response Heterogeneity**: Public datasets do not contain the specific multi-channel intervention responses (SMS vs WhatsApp vs Email) required to train the GRU effectively.
3. **Reproducibility**: The synthetic generator guarantees the benchmark can run offline without external dependencies, maintaining strict isolation between the ML predictions and the Oracle evaluation bounds.

No proprietary Razorpay data, leaked credentials, or scraped customer information was used in this project.
