# Training Pipeline

- **Temporal Split**: Train (Months 1-8), Val (Months 9-10), Test (Months 11-12).
- **Loss Function**: Binary Cross Entropy applied across the cumulative distribution (CDF) for all 5 horizons simultaneously.
- **Feature Space**: 10 Tabular features, 3 Sequential features (failure history, action encoding).