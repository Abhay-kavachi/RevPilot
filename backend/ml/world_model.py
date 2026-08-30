"""
World Model: Causal Synthetic Data Generator for RevPilot ML Pipeline.

Generates potential outcomes for ALL candidate recovery actions independently.
Uses the REAL EconomicPolicy action space from policy.json as the single source of truth.

All monetary values are INTEGER PAISE.
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import uuid
import os
import sys
import json
import hashlib

# Allow importing policy
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app.core.policy import PolicyManager

# ==========================================
# Configuration (not hardcoded in logic)
# ==========================================
NUM_CUSTOMERS = 25000
NUM_MERCHANTS = 1000
NUM_CASES = 200000
START_DATE = datetime(2025, 1, 1)
END_DATE = datetime(2025, 12, 31)
HORIZONS = [1, 6, 24, 72, 168]  # hours

def load_actions_from_policy():
    """Load the canonical action list from the real policy.json."""
    pm = PolicyManager()
    actions = list(pm.economic_policy.action_costs_paise.keys())
    costs_paise = pm.economic_policy.action_costs_paise
    return actions, costs_paise

def generate_entities(seed):
    rng = np.random.default_rng(seed)
    print("Generating entities...")
    customers = pd.DataFrame({
        "customer_id": [str(uuid.uuid4()) for _ in range(NUM_CUSTOMERS)],
        "base_reliability": rng.beta(2, 5, NUM_CUSTOMERS),
        "responsiveness": rng.beta(5, 2, NUM_CUSTOMERS),
    })
    merchants = pd.DataFrame({
        "merchant_id": [str(uuid.uuid4()) for _ in range(NUM_MERCHANTS)],
        "avg_ticket_paise": (rng.lognormal(mean=7, sigma=1, size=NUM_MERCHANTS).astype(int) * 100),
    })
    return customers, merchants

def generate_cases(customers, merchants, actions, seed):
    rng = np.random.default_rng(seed)
    print("Generating cases...")
    total_seconds = int((END_DATE - START_DATE).total_seconds())
    case_times = START_DATE + pd.to_timedelta(rng.integers(0, total_seconds, NUM_CASES), unit="s")
    case_times = pd.Series(case_times).sort_values().reset_index(drop=True)

    c_idx = rng.integers(0, NUM_CUSTOMERS, NUM_CASES)
    m_idx = rng.integers(0, NUM_MERCHANTS, NUM_CASES)

    # Assign preferred action from non-NO_ACTION actions
    active_actions = [a for a in actions if a != "NO_ACTION"]
    pref = rng.choice(active_actions, NUM_CUSTOMERS)

    cases = pd.DataFrame({
        "case_id": [str(uuid.uuid4()) for _ in range(NUM_CASES)],
        "customer_id": customers.iloc[c_idx]["customer_id"].values,
        "merchant_id": merchants.iloc[m_idx]["merchant_id"].values,
        "base_reliability": customers.iloc[c_idx]["base_reliability"].values,
        "responsiveness": customers.iloc[c_idx]["responsiveness"].values,
        "preferred_action": pref[c_idx],
        "amount_at_risk_paise": (merchants.iloc[m_idx]["avg_ticket_paise"].values * rng.lognormal(0, 0.2, NUM_CASES)).astype(int),
        "failed_at": case_times,
    })
    return cases

def sample_time_to_recovery(rng, base_rel, resp, pref_action, action, amount_paise, tom_factor, recent_failures):
    """Structural causal equation for time-to-recovery (hours)."""
    hz = 0.01 + 0.1 * base_rel
    hz *= max(1.0 - 0.1 * min(recent_failures, 5), 0.1)
    hz *= tom_factor

    # Action effectiveness multipliers (heterogeneous treatment effects)
    action_mults = {
        "NO_ACTION": 0.5,
        "SEND_REMINDER": 1.3,
        "RETRY_PAYMENT": 1.8,
        "CREATE_PAYMENT_LINK": 2.5,
        "ESCALATE_TO_SUPPORT": 1.0,
    }
    action_mult = action_mults.get(action, 1.0)

    if action == pref_action:
        action_mult *= 1.5 * resp

    hz *= action_mult
    hz *= (50000 / max(amount_paise, 1000)) ** 0.2

    ttr = rng.exponential(1.0 / max(hz, 0.001))

    if rng.random() > (base_rel + 0.2) * (action_mult ** 0.5):
        ttr = np.inf

    return ttr

def generate_events(cases, actions, seed):
    rng = np.random.default_rng(seed)
    print("Generating sequential events with potential outcomes...")
    events = []
    cust_failures = {cid: [] for cid in cases["customer_id"].unique()}

    # Historical policy weights (roughly uniform, slight bias to cheaper actions)
    n_actions = len(actions)
    policy_weights = np.ones(n_actions) / n_actions

    count = 0
    for _, row in cases.iterrows():
        count += 1
        if count % 20000 == 0:
            print(f"  Processed {count}/{NUM_CASES} cases")

        cid = row["customer_id"]
        t = row["failed_at"]

        past_failures = [pt for pt in cust_failures[cid] if (t - pt).days < 30]
        recent_fail_count = len(past_failures)
        cust_failures[cid].append(t)

        day = t.day
        tom_factor = 1.5 if day in [1, 2, 15, 16, 30, 31] else 1.0

        case_open = True
        current_time = t
        num_actions = rng.integers(1, 6)

        for step in range(num_actions):
            if not case_open:
                break

            chosen_action = rng.choice(actions, p=policy_weights)

            # Generate potential outcomes for ALL actions
            potential_outcomes = {}
            for a in actions:
                ttr = sample_time_to_recovery(
                    rng, row["base_reliability"], row["responsiveness"],
                    row["preferred_action"], a, row["amount_at_risk_paise"],
                    tom_factor, recent_fail_count,
                )
                po_horizons = {h: int(ttr <= h) for h in HORIZONS}
                potential_outcomes[a] = {"ttr": ttr, "horizons": po_horizons}

            realized_ttr = potential_outcomes[chosen_action]["ttr"]

            event_row = {
                "event_id": str(uuid.uuid4()),
                "case_id": row["case_id"],
                "customer_id": cid,
                "merchant_id": row["merchant_id"],
                "amount_at_risk_paise": row["amount_at_risk_paise"],
                "action_timestamp": current_time,
                "case_age_hours": (current_time - t).total_seconds() / 3600.0,
                "recent_30d_failures": recent_fail_count,
                "step": step,
                "action": chosen_action,
                "realized_ttr": realized_ttr,
            }

            for h in HORIZONS:
                event_row[f"target_{h}h"] = potential_outcomes[chosen_action]["horizons"][h]

            for a in actions:
                for h in HORIZONS:
                    event_row[f"oracle_{a}_{h}h"] = potential_outcomes[a]["horizons"][h]

            events.append(event_row)

            if realized_ttr <= 24:
                case_open = False
            else:
                current_time += timedelta(hours=24)

    return pd.DataFrame(events)

if __name__ == "__main__":
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 42
    print(f"World Model Seed: {seed}")

    actions, costs_paise = load_actions_from_policy()
    print(f"Actions from policy.json: {actions}")
    print(f"Action costs (paise): {costs_paise}")

    cust, merch = generate_entities(seed)
    cases = generate_cases(cust, merch, actions, seed)
    events_df = generate_events(cases, actions, seed)

    os.makedirs("data", exist_ok=True)
    out_path = f"data/world_model_events_seed{seed}.parquet"
    events_df.to_parquet(out_path, index=False)

    # Record provenance
    meta = {
        "seed": seed,
        "num_customers": NUM_CUSTOMERS,
        "num_merchants": NUM_MERCHANTS,
        "num_cases": NUM_CASES,
        "total_events": len(events_df),
        "actions": actions,
        "action_costs_paise": {k: v for k, v in costs_paise.items()},
        "horizons": HORIZONS,
        "date_range": f"{START_DATE.isoformat()} to {END_DATE.isoformat()}",
    }
    with open(f"data/world_model_meta_seed{seed}.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"World model complete. Events: {len(events_df)}. Saved to {out_path}")
