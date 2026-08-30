import pandas as pd
import numpy as np
import torch
from torch.utils.data import Dataset
from datetime import datetime

class RevPilotDataset(Dataset):
    def __init__(self, df, tabular_features, seq_length=5):
        self.df = df
        self.tabular_features = tabular_features
        self.seq_length = seq_length
        
        # Extract matrices
        self.tab_data = self.df[self.tabular_features].values.astype(np.float32)
        self.targets = self.df[['target_1h', 'target_6h', 'target_24h', 'target_72h', 'target_168h']].values.astype(np.float32)
        
        # Map actions to integers for the sequence
        actions_map = {"WAIT": 0, "EMAIL": 1, "SMS": 2, "WHATSAPP": 3, "CREATE_PAYMENT_LINK": 4, "RETRY_PAYMENT_OPPORTUNITY": 5}
        
        # We need a numeric representation for building sequences
        action_codes = np.zeros(len(self.df), dtype=int)
        for k, v in actions_map.items():
            col = f"action_{k}"
            if col in self.df.columns:
                action_codes[self.df[col] == 1] = v
                
        amounts = self.df["amount_at_risk"].values.astype(np.float32)
        timestamps = (self.df["action_timestamp"] - pd.Timestamp("1970-01-01")) // pd.Timedelta('1s')
        timestamps = timestamps.values
        customer_ids = self.df["customer_id"].values
        realized_ttr = self.df["realized_ttr"].values.astype(np.float32) * 3600 # convert hours to seconds
        
        # Sequence data: (Batch, Seq, Features)
        # Features: [amount, time_delta_hours, previous_action, recovered_by_now]
        self.seq_data = np.zeros((len(self.df), seq_length, 4), dtype=np.float32)
        
        # Build sequences (Vectorized/Grouped by customer)
        print(f"Building real temporal sequences for {len(self.df)} events...")
        
        # Ensure data is sorted by customer_id and timestamp
        sort_idx = np.lexsort((timestamps, customer_ids))
        
        # Inverse mapping to place sequences back into original dataframe order
        inv_sort_idx = np.empty_like(sort_idx)
        inv_sort_idx[sort_idx] = np.arange(len(sort_idx))
        
        sorted_cids = customer_ids[sort_idx]
        sorted_times = timestamps[sort_idx]
        sorted_amts = amounts[sort_idx]
        sorted_actions = action_codes[sort_idx]
        sorted_ttrs = realized_ttr[sort_idx]
        
        sorted_seq = np.zeros((len(self.df), seq_length, 4), dtype=np.float32)
        
        # Find group boundaries
        changes = np.where(sorted_cids[:-1] != sorted_cids[1:])[0] + 1
        starts = np.insert(changes, 0, 0)
        ends = np.append(changes, len(sorted_cids))
        
        for s, e in zip(starts, ends):
            # Iterate through customer's events
            for i in range(s, e):
                # i is the target index. History is [s : i]
                hist_len = min(i - s, seq_length)
                if hist_len > 0:
                    # from max(s, i - seq_length) to i
                    start_hist = max(s, i - seq_length)
                    hist_idx = np.arange(start_hist, i)
                    
                    # Fill the sequence from the end (right aligned padding)
                    target_start = seq_length - hist_len
                    
                    # Feature 0: Amount
                    sorted_seq[i, target_start:, 0] = sorted_amts[hist_idx]
                    
                    # Feature 1: Time delta (hours) between history event and CURRENT event
                    time_deltas = (sorted_times[i] - sorted_times[hist_idx]) / 3600.0
                    sorted_seq[i, target_start:, 1] = time_deltas
                    
                    # Feature 2: Previous Action
                    sorted_seq[i, target_start:, 2] = sorted_actions[hist_idx]
                    
                    # Feature 3: Was it recovered BEFORE the current event?
                    # The historical event occurred at `sorted_times[hist_idx]`.
                    # It recovers at `sorted_times[hist_idx] + sorted_ttrs[hist_idx]`.
                    # So if that recovery time <= `sorted_times[i]`, it was recovered.
                    recovery_times = sorted_times[hist_idx] + sorted_ttrs[hist_idx]
                    recovered = (recovery_times <= sorted_times[i]).astype(np.float32)
                    sorted_seq[i, target_start:, 3] = recovered
                    
        # Restore original order
        self.seq_data = sorted_seq[inv_sort_idx]
        
    def __len__(self):
        return len(self.df)
        
    def __getitem__(self, idx):
        return (
            torch.tensor(self.tab_data[idx]),
            torch.tensor(self.seq_data[idx]),
            torch.tensor(self.targets[idx])
        )

def prepare_data(filepath="data/world_model_events.parquet"):
    print(f"Loading data from {filepath}...")
    df = pd.read_parquet(filepath)
    
    # Sort by time to ensure strict temporal split
    df = df.sort_values("action_timestamp").reset_index(drop=True)
    
    # Encode categorical actions for tabular
    df = pd.get_dummies(df, columns=["action"])
    
    # Define tabular features (excluding any target leakage fields)
    tabular_features = [
        "amount_at_risk", 
        "case_age_hours",
        "recent_30d_failures",
        "step"
    ] + [c for c in df.columns if c.startswith("action_") and c != "action_timestamp"]
    
    # Normalize amount for neural nets
    df["amount_at_risk"] = np.log1p(df["amount_at_risk"])
    
    # Temporal Split:
    # Train: Months 1-8
    # Val: Months 9-10
    # Test: Months 11-12
    df['month'] = df['action_timestamp'].dt.month
    
    train_df = df[df['month'] <= 8].copy()
    val_df = df[(df['month'] >= 9) & (df['month'] <= 10)].copy()
    test_df = df[df['month'] >= 11].copy()
    
    print(f"Split sizes -> Train: {len(train_df)}, Val: {len(val_df)}, Test: {len(test_df)}")
    
    return train_df, val_df, test_df, tabular_features, df
