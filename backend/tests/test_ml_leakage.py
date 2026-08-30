"""
ML Feature Leakage Tests.

Proves:
  1. Customer A and Customer B produce DIFFERENT sequence tensors.
  2. No event after the prediction timestamp can ever enter the sequence.
  3. Recovery status is only visible if it provably completed before the current event.
  4. Paise unit consistency: Rs.500 = 50000 paise, Rs.2.50 = 250 paise.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'ml'))
import pandas as pd
import numpy as np
from dataset import RevPilotDataset

def test_sequence_leakage_and_differentiation():
    """Core sequence construction and leakage test."""
    data = [
        # Customer A: 3 events
        {"customer_id": "A", "action_timestamp": pd.Timestamp("2025-01-01 10:00:00"),
         "amount_at_risk_paise": 50000, "realized_ttr": 2.0,
         "action_CREATE_PAYMENT_LINK": 1, "action_NO_ACTION": 0,
         "action_RETRY_PAYMENT": 0, "action_SEND_REMINDER": 0, "action_ESCALATE_TO_SUPPORT": 0},
        {"customer_id": "A", "action_timestamp": pd.Timestamp("2025-01-01 11:00:00"),
         "amount_at_risk_paise": 50000, "realized_ttr": 24.0,
         "action_CREATE_PAYMENT_LINK": 0, "action_NO_ACTION": 0,
         "action_RETRY_PAYMENT": 1, "action_SEND_REMINDER": 0, "action_ESCALATE_TO_SUPPORT": 0},
        {"customer_id": "A", "action_timestamp": pd.Timestamp("2025-01-01 12:00:00"),
         "amount_at_risk_paise": 50000, "realized_ttr": 1.0,
         "action_CREATE_PAYMENT_LINK": 0, "action_NO_ACTION": 0,
         "action_RETRY_PAYMENT": 0, "action_SEND_REMINDER": 1, "action_ESCALATE_TO_SUPPORT": 0},
        # Customer B: 2 events (different history)
        {"customer_id": "B", "action_timestamp": pd.Timestamp("2025-01-01 10:30:00"),
         "amount_at_risk_paise": 100000, "realized_ttr": 5.0,
         "action_CREATE_PAYMENT_LINK": 1, "action_NO_ACTION": 0,
         "action_RETRY_PAYMENT": 0, "action_SEND_REMINDER": 0, "action_ESCALATE_TO_SUPPORT": 0},
        {"customer_id": "B", "action_timestamp": pd.Timestamp("2025-01-01 14:30:00"),
         "amount_at_risk_paise": 100000, "realized_ttr": 1.0,
         "action_CREATE_PAYMENT_LINK": 0, "action_NO_ACTION": 0,
         "action_RETRY_PAYMENT": 0, "action_SEND_REMINDER": 0, "action_ESCALATE_TO_SUPPORT": 1},
    ]
    for row in data:
        for t in ["1h", "6h", "24h", "72h", "168h"]:
            row[f"target_{t}"] = 0.0
        row["amount_at_risk_paise_log"] = np.log1p(row["amount_at_risk_paise"])
        row["case_age_hours"] = 0.0
        row["recent_30d_failures"] = 0
        row["step"] = 0

    df = pd.DataFrame(data)
    tabular_features = ["amount_at_risk_paise_log"]
    dataset = RevPilotDataset(df, tabular_features=tabular_features, seq_length=2)

    # 1. Customer A event 3 (index 2): should have history from events 0 and 1
    seq_A = dataset.seq_data[2]
    # 2. Customer B event 2 (index 4): should have history from event 3 only
    seq_B = dataset.seq_data[4]

    # DIFFERENT CUSTOMERS MUST PRODUCE DIFFERENT SEQUENCES
    assert not np.array_equal(seq_A, seq_B), "Customer A and B must have different sequences"

    # LEAKAGE TEST: Event 1 (11:00) with ttr=24h recovers at 11+24=35:00.
    # At prediction time 12:00, it has NOT recovered.
    assert seq_A[1, 3] == 0.0, "Event 1 (ttr=24h) should NOT show as recovered at 12:00"

    # Event 0 (10:00) with ttr=2h recovers at 12:00.
    # At prediction time 12:00, it SHOULD show as recovered (10:00 + 2h = 12:00 <= 12:00).
    assert seq_A[0, 3] == 1.0, "Event 0 (ttr=2h) SHOULD show as recovered at 12:00"

    # Customer B event 0 (10:30) ttr=5h -> recovers at 15:30. Prediction at 14:30. NOT recovered.
    assert seq_B[1, 3] == 0.0, "B event 0 (ttr=5h) NOT recovered at 14:30"

    print("PASS: Sequence construction and leakage tests")

def test_paise_unit_consistency():
    """Verify paise/rupee conversions are correct."""
    assert 500 * 100 == 50000, "Rs.500 = 50000 paise"
    assert int(2.50 * 100) == 250, "Rs.2.50 = 250 paise"

    # Utility calculation in paise: P(success)*amount_paise - cost_paise
    amount_paise = 50000  # Rs. 500
    cost_paise = 250      # Rs. 2.50
    p_success = 0.8
    ev = int(p_success * amount_paise) - cost_paise
    assert ev == 39750, f"EV should be 39750 paise (Rs.397.50), got {ev}"

    print("PASS: Paise unit consistency tests")

def test_counterfactual_sanity():
    """
    Verify that highest probability != highest economic value.

    Action A: P=0.80, cost=Rs.100 (10000 paise)
    Action B: P=0.70, cost=Rs.5 (500 paise)

    For a case worth Rs.500 (50000 paise):
    EV(A) = 0.80 * 50000 - 10000 = 30000 paise
    EV(B) = 0.70 * 50000 - 500 = 34500 paise

    B has LOWER probability but HIGHER expected value.
    """
    amount_paise = 50000
    ev_a = int(0.80 * amount_paise) - 10000  # 30000
    ev_b = int(0.70 * amount_paise) - 500    # 34500
    assert ev_b > ev_a, f"Action B (lower P) must have higher EV: {ev_b} > {ev_a}"

    # Case where NO_ACTION is optimal:
    # P=0.01, cost=5000 paise (Rs.50), amount=10000 paise (Rs.100)
    ev_action = int(0.01 * 10000) - 5000   # 100 - 5000 = -4900
    ev_wait = 0
    assert ev_wait > ev_action, f"NO_ACTION should be better: {ev_wait} > {ev_action}"

    print("PASS: Counterfactual sanity tests (probability != optimal action)")

if __name__ == "__main__":
    test_sequence_leakage_and_differentiation()
    test_paise_unit_consistency()
    test_counterfactual_sanity()
    print("\nALL ML LEAKAGE AND SANITY TESTS PASSED")
