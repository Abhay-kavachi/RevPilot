import pandas as pd
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
from datetime import datetime

class RevPilotDataset(Dataset):
    def __init__(self, df, tabular_features, seq_length=5):
        self.df = df
        self.tabular_features = tabular_features
        self.seq_length = seq_length
        
        # Extract matrices for fast access
        self.tab_data = self.df[self.tabular_features].values.astype(np.float32)
        
        # Multi-horizon targets (1h, 6h, 24h, 72h, 168h)
        self.targets = self.df[['target_1h', 'target_6h', 'target_24h', 'target_72h', 'target_168h']].values.astype(np.float32)
        
        # Sequence data: for now, we just pad with zeros since it's tricky to build full seq 
        # iteratively in a simple script without grouping. 
        # But for the world model, we generated rows where `recent_30d_failures` acts as a historical proxy.
        # Let's create a dummy sequence of length `seq_length` to represent history.
        # Real implementation would group by customer_id and take rolling windows.
        # For prototype: (Batch, Seq, Features)
        self.seq_data = np.zeros((len(self.df), seq_length, 3), dtype=np.float32)
        
        
        # Populate sequence data
        failures = self.df['recent_30d_failures'].values.astype(int)
        
        # Extract action indices
        actions_map = {"WAIT": 0, "EMAIL": 1, "SMS": 2, "WHATSAPP": 3, "CREATE_PAYMENT_LINK": 4, "RETRY_PAYMENT_OPPORTUNITY": 5}
        act_idx = np.zeros(len(self.df), dtype=int)
        for k, v in actions_map.items():
            col = f"action_{k}"
            if col in self.df.columns:
                act_idx[self.df[col] == 1] = v
                
        for i in range(len(self.df)):
            # fill recent steps with failure indicators
            f_count = min(failures[i], seq_length)
            if f_count > 0:
                self.seq_data[i, -f_count-1:-1, 0] = 1.0 # failure indicator
                
            # current action
            self.seq_data[i, -1, 1] = act_idx[i]
            
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
    
    # Encode categorical actions
    df = pd.get_dummies(df, columns=["action"])
    
    # Define tabular features
    tabular_features = [
        "amount_at_risk", 
        "case_age_hours",
        "recent_30d_failures",
        "step"
    ] + [c for c in df.columns if c.startswith("action_") and c != "action_timestamp"]
    
    # Normalize amount
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
    
    return train_df, val_df, test_df, tabular_features
