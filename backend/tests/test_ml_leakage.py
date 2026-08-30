import pandas as pd
import numpy as np
import sys
import os

# Ensure backend can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'ml')))
from dataset import RevPilotDataset

def test_sequence_construction_and_leakage():
    # Construct a dummy dataset representing 2 customers over time
    data = [
        # Customer A
        {"customer_id": "A", "action_timestamp": pd.Timestamp("2025-01-01 10:00:00"), "amount_at_risk": 100.0, "realized_ttr": 2.0, "action_WAIT": 1},
        {"customer_id": "A", "action_timestamp": pd.Timestamp("2025-01-01 11:00:00"), "amount_at_risk": 100.0, "realized_ttr": 24.0, "action_WAIT": 0},
        {"customer_id": "A", "action_timestamp": pd.Timestamp("2025-01-01 12:00:00"), "amount_at_risk": 100.0, "realized_ttr": 1.0, "action_WAIT": 0},
        
        # Customer B
        {"customer_id": "B", "action_timestamp": pd.Timestamp("2025-01-01 10:30:00"), "amount_at_risk": 500.0, "realized_ttr": 5.0, "action_WAIT": 1},
        {"customer_id": "B", "action_timestamp": pd.Timestamp("2025-01-01 14:30:00"), "amount_at_risk": 500.0, "realized_ttr": 1.0, "action_WAIT": 1},
    ]
    
    # Add dummy target columns
    for row in data:
        for t in ["1h", "6h", "24h", "72h", "168h"]:
            row[f"target_{t}"] = 0.0
            
    df = pd.DataFrame(data)
    
    dataset = RevPilotDataset(df, tabular_features=["amount_at_risk"], seq_length=2)
    
    # Check Customer A's 3rd event (Index 2)
    seq_A_event3 = dataset.seq_data[2]
    # Sequence length 2. Should contain Event 1 and Event 2 for Customer A.
    # Event 1: 10:00:00, Event 3: 12:00:00 -> Time Delta = 2.0 hours
    # Event 2: 11:00:00, Event 3: 12:00:00 -> Time Delta = 1.0 hours
    assert seq_A_event3[0, 1] == 2.0 # Time delta for first history
    assert seq_A_event3[1, 1] == 1.0 # Time delta for second history
    
    # Check leakage: Did it know Event 2 recovered?
    # Event 2 occurred at 11:00, with realized_ttr 24h. 
    # Current time is 12:00. So at 12:00, 11+24 = 35 != recovered yet.
    assert seq_A_event3[1, 3] == 0.0 # Not recovered
    
    # Did it know Event 1 recovered?
    # Event 1 occurred at 10:00, realized_ttr 2.0h.
    # Current time is 12:00. 10+2 = 12:00. Yes, it recovered exactly now.
    assert seq_A_event3[0, 3] == 1.0 # Recovered
    
    # Check Customer B's 2nd event (Index 4)
    seq_B_event2 = dataset.seq_data[4]
    # History should only have Event B1. Index 0 is padded with 0.
    assert seq_B_event2[0, 0] == 0.0 # Amount is 0 (padded)
    assert seq_B_event2[1, 0] == 500.0 # Amount for B1
    assert seq_B_event2[1, 1] == 4.0 # Time Delta 14:30 - 10:30 = 4.0h
    
    # Event B1 recovered? TTR = 5h. 10:30 + 5h = 15:30. Current time 14:30.
    assert seq_B_event2[1, 3] == 0.0 # Not recovered yet
    
    print("Leakage and sequence construction tests PASSED!")

if __name__ == "__main__":
    test_sequence_construction_and_leakage()
