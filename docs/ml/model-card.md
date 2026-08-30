# Model Card: RevPilot Hybrid v1

- **Type**: PyTorch Hybrid (MLP + GRU)
- **Intended Use**: Rank recovery actions by expected value in the RevPilot Economic Engine.
- **Limitations**: Trained on synthetic data. Requires recalibration (Isotonic) before live production use.