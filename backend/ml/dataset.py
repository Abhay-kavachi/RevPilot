"""
RevPilot ML Dataset Loader.

Builds REAL temporal customer sequences using chronological grouping.
All monetary values remain in INTEGER PAISE.

Sequence features per historical event:
  [0] amount_at_risk_paise (log-normalized)
  [1] time_delta_hours (time between history event and current event)
  [2] action_code (integer encoding of the action taken)
  [3] recovered_before_current (1.0 if the historical event recovered before the current timestamp)
"""
import pandas as pd
import numpy as np
import torch
from torch.utils.data import Dataset
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app.core.policy import PolicyManager

def _load_actions():
    pm = PolicyManager()
    return list(pm.economic_policy.action_costs_paise.keys())

class RevPilotDataset(Dataset):
    def __init__(self, df, tabular_features, seq_length=5):
        self.df = df.reset_index(drop=True)
        self.tabular_features = tabular_features
        self.seq_length = seq_length

        self.tab_data = self.df[self.tabular_features].values.astype(np.float32)
        self.targets = self.df[['target_1h', 'target_6h', 'target_24h', 'target_72h', 'target_168h']].values.astype(np.float32)

        # Build action code mapping from policy
        actions = _load_actions()
        actions_map = {a: i for i, a in enumerate(actions)}

        action_codes = np.zeros(len(self.df), dtype=int)
        for k, v in actions_map.items():
            col = f"action_{k}"
            if col in self.df.columns:
                action_codes[self.df[col] == 1] = v

        amounts = self.df["amount_at_risk_paise"].values.astype(np.float32)
        timestamps = (self.df["action_timestamp"] - pd.Timestamp("1970-01-01")) // pd.Timedelta('1s')
        timestamps = timestamps.values
        customer_ids = self.df["customer_id"].values
        realized_ttr = self.df["realized_ttr"].values.astype(np.float32) * 3600  # hours to seconds

        self.seq_data = np.zeros((len(self.df), seq_length, 4), dtype=np.float32)

        print(f"  Building real temporal sequences for {len(self.df)} events...")

        sort_idx = np.lexsort((timestamps, customer_ids))
        inv_sort_idx = np.empty_like(sort_idx)
        inv_sort_idx[sort_idx] = np.arange(len(sort_idx))

        sorted_cids = customer_ids[sort_idx]
        sorted_times = timestamps[sort_idx]
        sorted_amts = amounts[sort_idx]
        sorted_actions = action_codes[sort_idx]
        sorted_ttrs = realized_ttr[sort_idx]

        sorted_seq = np.zeros((len(self.df), seq_length, 4), dtype=np.float32)

        changes = np.where(sorted_cids[:-1] != sorted_cids[1:])[0] + 1
        starts = np.insert(changes, 0, 0)
        ends = np.append(changes, len(sorted_cids))

        for s, e in zip(starts, ends):
            for i in range(s, e):
                hist_len = min(i - s, seq_length)
                if hist_len > 0:
                    start_hist = max(s, i - seq_length)
                    hist_idx = np.arange(start_hist, i)
                    target_start = seq_length - hist_len

                    sorted_seq[i, target_start:, 0] = np.log1p(sorted_amts[hist_idx])
                    time_deltas = (sorted_times[i] - sorted_times[hist_idx]) / 3600.0
                    sorted_seq[i, target_start:, 1] = time_deltas
                    sorted_seq[i, target_start:, 2] = sorted_actions[hist_idx]
                    recovery_times = sorted_times[hist_idx] + sorted_ttrs[hist_idx]
                    recovered = (recovery_times <= sorted_times[i]).astype(np.float32)
                    sorted_seq[i, target_start:, 3] = recovered

        self.seq_data = sorted_seq[inv_sort_idx]

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        return (
            torch.tensor(self.tab_data[idx]),
            torch.tensor(self.seq_data[idx]),
            torch.tensor(self.targets[idx]),
        )

def prepare_data(filepath=None):
    if filepath is None:
        filepath = os.path.join(os.path.dirname(__file__), '..', 'data', 'world_model_events_seed42.parquet')
    print(f"Loading data from {filepath}...")
    df = pd.read_parquet(filepath)
    df = df.sort_values("action_timestamp").reset_index(drop=True)

    # One-hot encode actions
    df = pd.get_dummies(df, columns=["action"])

    # Enforce static FeatureSchema
    from ml.features import FeatureSchema
    tabular_features = FeatureSchema.features
    
    # Ensure all required one-hot columns exist (even if 0 occurrences in this fold)
    for col in tabular_features:
        if col not in df.columns:
            df[col] = 0.0

    df["amount_at_risk_paise_log"] = np.log1p(df["amount_at_risk_paise"])

    df['month'] = df['action_timestamp'].dt.month
    train_df = df[df['month'] <= 8].copy()
    val_df = df[(df['month'] >= 9) & (df['month'] <= 10)].copy()
    test_df = df[df['month'] >= 11].copy()

    print(f"  Split sizes -> Train: {len(train_df)}, Val: {len(val_df)}, Test: {len(test_df)}")
    return train_df, val_df, test_df, tabular_features
