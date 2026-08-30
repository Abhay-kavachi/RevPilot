# Model Selection Rule

> This document defines the selection criteria BEFORE the final model comparison is run.
> The winning model is determined by this rule applied to the empirical results.
> No post-hoc rationalization.

## Selection Hierarchy

### 1. PRIMARY: Out-of-Time Decision Utility / Regret (Weight: 40%)

The model whose calibrated probability estimates produce the lowest **Regret** (Oracle Utility - Strategy Utility) on the held-out OOT test set (Months 11-12) is preferred.

Regret is measured in **integer paise** using the exact action costs from `policy.json`.

### 2. SECONDARY: Probability Calibration (Weight: 25%)

Among models with comparable regret (within 5% relative), the model with the lowest **Brier Score** on the 72-hour horizon is preferred. Brier score directly measures calibration quality.

### 3. TERTIARY: Predictive Discrimination (Weight: 20%)

If regret and calibration are comparable, prefer the model with the highest **PR-AUC** at the 72-hour horizon (PR-AUC is more informative than ROC-AUC for imbalanced early horizons).

### 4. STABILITY: Multi-Seed Variance (Weight: 10%)

Among otherwise equivalent models, prefer the one with the **lowest standard deviation** of regret across seeds 42, 123, 2024.

### 5. EFFICIENCY: Inference Latency (Weight: 5%)

Among otherwise equivalent models, prefer the one with the **lowest inference time** per batch.

## Tie-Breaking Rules

- If LightGBM and a neural model produce equivalent decision utility, **LightGBM wins** (simpler, faster, more interpretable).
- If the Transformer does not materially improve over the GRU, **remove the Transformer** from the final system.
- A model with slightly worse AUC **can win** if it produces better calibrated economic decisions.

## Disqualification Criteria

A model is disqualified if:
- It produces **negative net utility** on the test set.
- Its Brier Score is **worse than the marginal frequency baseline**.
- It exhibits **monotonicity violations** after calibration.
- Its predictions are **invariant to action conditioning** (same prediction regardless of action).

## Final Disclosure

The selected model must be defensible to a Razorpay engineer:

> "We trained five competing models, evaluated them on future unseen data,
> calibrated them on validation-only, tested decision regret against a hidden
> counterfactual world, and integrated only the model that empirically
> created the best economic decisions."
