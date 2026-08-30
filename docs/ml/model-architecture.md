# Model Architecture

- **Tabular Baseline**: LightGBM (100 estimators, 0.05 LR)
- **Temporal Model**: PyTorch GRU (Hidden Dim 64)
- **Hybrid Fusion**: Tabular MLP + GRU output concatenated into a Multi-Horizon Monotonic CDF Head.
- **Prediction Targets**: P(recovery | 1h, 6h, 24h, 3d, 7d)
- **Constraint**: Monotonicity enforced via cumulative survival hazard estimation.