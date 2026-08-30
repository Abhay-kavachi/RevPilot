import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import uuid
import os

np.random.seed(42)

NUM_CUSTOMERS = 25000
NUM_MERCHANTS = 1000
NUM_CASES = 200000 
START_DATE = datetime(2025, 1, 1)
END_DATE = datetime(2025, 12, 31)

ACTIONS = ["WAIT", "EMAIL", "SMS", "WHATSAPP", "CREATE_PAYMENT_LINK", "RETRY_PAYMENT_OPPORTUNITY"]
HORIZONS = [1, 6, 24, 72, 168] # in hours (1h, 6h, 24h, 3d, 7d)

def generate_entities():
    print("Generating entities...")
    customers = pd.DataFrame({
        "customer_id": [str(uuid.uuid4()) for _ in range(NUM_CUSTOMERS)],
        "base_reliability": np.random.beta(2, 5, NUM_CUSTOMERS),
        "responsiveness": np.random.beta(5, 2, NUM_CUSTOMERS),
        "preferred_action": np.random.choice(ACTIONS[1:], NUM_CUSTOMERS)
    })
    
    merchants = pd.DataFrame({
        "merchant_id": [str(uuid.uuid4()) for _ in range(NUM_MERCHANTS)],
        "avg_ticket": np.random.lognormal(mean=7, sigma=1, size=NUM_MERCHANTS).astype(int) * 100 # paise
    })
    return customers, merchants

def generate_cases(customers, merchants):
    print("Generating cases...")
    # distribute cases temporally
    total_seconds = int((END_DATE - START_DATE).total_seconds())
    case_times = START_DATE + pd.to_timedelta(np.random.randint(0, total_seconds, NUM_CASES), unit="s")
    case_times = pd.Series(case_times).sort_values().reset_index(drop=True)
    
    c_idx = np.random.randint(0, NUM_CUSTOMERS, NUM_CASES)
    m_idx = np.random.randint(0, NUM_MERCHANTS, NUM_CASES)
    
    cases = pd.DataFrame({
        "case_id": [str(uuid.uuid4()) for _ in range(NUM_CASES)],
        "customer_id": customers.iloc[c_idx]["customer_id"].values,
        "merchant_id": merchants.iloc[m_idx]["merchant_id"].values,
        "base_reliability": customers.iloc[c_idx]["base_reliability"].values,
        "responsiveness": customers.iloc[c_idx]["responsiveness"].values,
        "preferred_action": customers.iloc[c_idx]["preferred_action"].values,
        "amount_at_risk": (merchants.iloc[m_idx]["avg_ticket"].values * np.random.lognormal(0, 0.2, NUM_CASES)).astype(int),
        "failed_at": case_times
    })
    return cases

def sample_time_to_recovery(base_rel, resp, pref_action, action, amount, time_of_month_factor, recent_failures):
    # Causal structural equation for recovery time
    # Hazard rate lambda
    # base hazard
    hz = 0.01 + 0.1 * base_rel 
    hz *= (1.0 - 0.1 * min(recent_failures, 5)) # penalty for recent failures
    hz *= time_of_month_factor
    
    # action modifier
    action_mult = 1.0
    if action == "WAIT":
        action_mult = 0.5
    elif action == "EMAIL":
        action_mult = 1.2
    elif action == "SMS":
        action_mult = 1.5
    elif action == "WHATSAPP":
        action_mult = 2.0
    elif action == "CREATE_PAYMENT_LINK":
        action_mult = 2.5
    elif action == "RETRY_PAYMENT_OPPORTUNITY":
        action_mult = 3.0
        
    # personalized modifier
    if action == pref_action:
        action_mult *= 1.5 * resp
        
    hz *= action_mult
    
    # Large amounts take longer
    hz *= (50000 / max(amount, 1000))**0.2
    
    # sample from exponential
    ttr = np.random.exponential(1.0 / max(hz, 0.001))
    
    # Sometimes they NEVER recover (inf)
    if np.random.rand() > (base_rel + 0.2) * (action_mult**0.5):
        ttr = np.inf
        
    return ttr

def generate_events(cases):
    print("Generating sequential events with potential outcomes...")
    events = []
    
    # Tracking customer history
    cust_failures = {cid: [] for cid in cases["customer_id"].unique()}
    
    count = 0
    for _, row in cases.iterrows():
        count += 1
        if count % 10000 == 0:
            print(f"Processed {count}/{NUM_CASES} cases")
            
        cid = row["customer_id"]
        t = row["failed_at"]
        
        # update customer history
        past_failures = [pt for pt in cust_failures[cid] if (t - pt).days < 30]
        recent_fail_count = len(past_failures)
        cust_failures[cid].append(t)
        
        # Payday effect (1st or 15th)
        day = t.day
        tom_factor = 1.5 if day in [1, 2, 15, 16, 30, 31] else 1.0
        
        case_open = True
        current_time = t
        
        # Simulating a historical policy taking up to 5 actions
        num_actions = np.random.randint(1, 6)
        
        for step in range(num_actions):
            if not case_open:
                break
                
            # Random historical policy selects an action (biased slightly to cheaper actions)
            chosen_action = np.random.choice(ACTIONS, p=[0.2, 0.25, 0.2, 0.15, 0.1, 0.1])
            
            # Generate POTENTIAL OUTCOMES for all actions (Oracle Counterfactuals)
            potential_outcomes = {}
            for a in ACTIONS:
                ttr = sample_time_to_recovery(
                    row["base_reliability"], row["responsiveness"], row["preferred_action"],
                    a, row["amount_at_risk"], tom_factor, recent_fail_count
                )
                
                po_horizons = {h: int(ttr <= h) for h in HORIZONS}
                potential_outcomes[a] = {
                    "ttr": ttr,
                    "horizons": po_horizons
                }
            
            # The realized outcome is the one for the chosen action
            realized_ttr = potential_outcomes[chosen_action]["ttr"]
            
            # Extract horizons for the event row
            event_row = {
                "event_id": str(uuid.uuid4()),
                "case_id": row["case_id"],
                "customer_id": cid,
                "merchant_id": row["merchant_id"],
                "amount_at_risk": row["amount_at_risk"],
                "action_timestamp": current_time,
                "case_age_hours": (current_time - t).total_seconds() / 3600.0,
                "recent_30d_failures": recent_fail_count,
                "step": step,
                "action": chosen_action,
                "realized_ttr": realized_ttr
            }
            
            # Add realized horizon targets
            for h in HORIZONS:
                event_row[f"target_{h}h"] = potential_outcomes[chosen_action]["horizons"][h]
                
            # Add oracle potential outcomes for regret computation
            for a in ACTIONS:
                for h in HORIZONS:
                    event_row[f"oracle_{a}_{h}h"] = potential_outcomes[a]["horizons"][h]
            
            events.append(event_row)
            
            # If the realized TTR is small enough, the case is recovered before the next step
            # Let's say the next step is scheduled in 24 hours
            if realized_ttr <= 24:
                case_open = False
            else:
                current_time += timedelta(hours=24)
                
    return pd.DataFrame(events)

if __name__ == "__main__":
    cust, merch = generate_entities()
    cases = generate_cases(cust, merch)
    events_df = generate_events(cases)
    
    os.makedirs("data", exist_ok=True)
    events_df.to_parquet("data/world_model_events.parquet", index=False)
    print(f"World model generation complete. Total events: {len(events_df)}")
    print("Saved to data/world_model_events.parquet")
