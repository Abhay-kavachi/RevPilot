# Ablation Report (Phase 2)

## Core Findings
- **Sequence History**: The PyTorch GRU using real sliding windows (Amount, Delta, Action, Prior Outcome) strongly differentiates users with clustered failures versus simple one-offs.
- **Temporal Split**: By strictly slicing on Month 1-8 (Train), 9-10 (Val), and 11-12 (Test), we observed that temporal drifts decay LightGBM performance slightly faster than the GRU sequence model, which adapts better to the chronological context of the user.