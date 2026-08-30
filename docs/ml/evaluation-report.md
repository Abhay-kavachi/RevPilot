# Out-of-Time Evaluation Report

### LightGBM Baseline (72h)
- AUC: 0.692
- PR-AUC: 0.660
- Brier: 0.221

### Hybrid (Tabular + GRU) (72h)
- AUC: 0.694
- PR-AUC: 0.661
- Brier: 0.222

Conclusion: Hybrid model slightly outperforms LightGBM on PR-AUC and ROC-AUC. Full decision utility evaluation requires the Policy Engine scorer.