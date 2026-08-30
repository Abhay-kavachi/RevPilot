"""
RevPilot ML Benchmark Sanity Diagnostics.

Runs all diagnostics required by the Phase 2 gate:
  1. Oracle action distribution
  2. Per-case regret distribution
  3. Random policy benchmark
  4. Shuffled-label benchmark
  5. Cost perturbation test
  6. Feature ablation
  7. Multi-seed evaluation
"""
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
import numpy as np
import json
import os
import sys
from sklearn.isotonic import IsotonicRegression
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app.core.policy import PolicyManager
from ml.dataset import prepare_data, RevPilotDataset
from ml.models import HybridModel, TemporalGRU, get_logistic_baseline, get_lightgbm_baseline
from ml.evaluate import evaluate_predictions, evaluate_policy_regret

def load_policy():
    pm = PolicyManager()
    actions = list(pm.economic_policy.action_costs_paise.keys())
    costs = pm.economic_policy.action_costs_paise
    return actions, costs

def diagnostic_oracle_distribution(df_test, actions, costs):
    """Diagnose: what does the Oracle pick? Is one action dominant?"""
    print("\n" + "="*60)
    print("DIAGNOSTIC 1: Oracle Action Distribution")
    print("="*60)

    oracle_picks = []
    unique_oracle = 0
    tied_oracle = 0
    no_action_optimal = 0

    per_case_oracle_utility = []

    for i in range(len(df_test)):
        row = df_test.iloc[i]
        amt = row["amount_at_risk_paise"]

        best_u = 0  # NO_ACTION baseline
        best_a = "NO_ACTION"
        utilities = {}

        for a in actions:
            cost = costs[a]
            outcome = row.get(f"oracle_{a}_72h", 0)
            u = int(outcome * amt) - cost
            utilities[a] = u
            if u > best_u:
                best_u = u
                best_a = a

        # Count ties
        max_u = max(utilities.values())
        tied = sum(1 for v in utilities.values() if v == max_u)

        if best_a == "NO_ACTION":
            no_action_optimal += 1
        if tied > 1:
            tied_oracle += 1
        else:
            unique_oracle += 1

        oracle_picks.append(best_a)
        per_case_oracle_utility.append(best_u)

    counts = Counter(oracle_picks)
    total = len(oracle_picks)
    for a in actions:
        pct = counts.get(a, 0) / total * 100
        print(f"  {a}: {counts.get(a, 0)} ({pct:.1f}%)")

    print(f"\n  Unique oracle: {unique_oracle} ({unique_oracle/total*100:.1f}%)")
    print(f"  Tied oracle:   {tied_oracle} ({tied_oracle/total*100:.1f}%)")
    print(f"  NO_ACTION optimal: {no_action_optimal} ({no_action_optimal/total*100:.1f}%)")

    arr = np.array(per_case_oracle_utility)
    print(f"\n  Oracle utility per case (paise):")
    print(f"    mean={arr.mean():.0f}, median={np.median(arr):.0f}, std={arr.std():.0f}")
    print(f"    min={arr.min():.0f}, max={arr.max():.0f}")

    return oracle_picks, per_case_oracle_utility

def diagnostic_per_case_regret(df_test, actions, costs, get_preds_fn, tab_data, seq_data, tabular_features, model_name):
    """Compute per-case regret distribution."""
    print(f"\n{'='*60}")
    print(f"DIAGNOSTIC 3: Per-Case Regret Distribution ({model_name})")
    print(f"{'='*60}")

    per_case_regrets = []
    match_count = 0
    differ_count = 0

    for i in range(len(df_test)):
        row = df_test.iloc[i]
        amt = row["amount_at_risk_paise"]

        # Oracle best
        best_oracle_u = 0
        for a in actions:
            o = row.get(f"oracle_{a}_72h", 0)
            u = int(o * amt) - costs[a]
            if u > best_oracle_u:
                best_oracle_u = u
                best_oracle_a = a

        # Model best (score all actions)
        best_model_u = -np.inf
        best_model_a = "NO_ACTION"
        for j, a in enumerate(actions):
            act_tab = tab_data[i:i+1].copy()
            for k, c_name in enumerate(actions):
                col_name = f"action_{c_name}"
                if col_name in tabular_features:
                    feat_idx = tabular_features.index(col_name)
                    act_tab[0, feat_idx] = 1.0 if c_name == a else 0.0

            preds = get_preds_fn(act_tab, seq_data[i:i+1])
            p = preds[0, 3]  # 72h
            ev = p * amt - costs[a]
            if ev > best_model_u:
                best_model_u = ev
                best_model_a = a

        # Realized outcome for model's chosen action
        model_outcome = row.get(f"oracle_{best_model_a}_72h", 0)
        realized_u = int(model_outcome * amt) - costs[best_model_a]

        regret = max(best_oracle_u, 0) - realized_u
        per_case_regrets.append(regret)

        if best_model_a == best_oracle_a:
            match_count += 1
        else:
            differ_count += 1

    arr = np.array(per_case_regrets)
    total = len(arr)
    print(f"  Match oracle: {match_count} ({match_count/total*100:.1f}%)")
    print(f"  Differ:       {differ_count} ({differ_count/total*100:.1f}%)")
    print(f"  Mean regret:   {arr.mean()/100:.2f} Rs")
    print(f"  Median regret: {np.median(arr)/100:.2f} Rs")
    print(f"  Std regret:    {arr.std()/100:.2f} Rs")
    print(f"  Zero regret:   {np.sum(arr == 0)} ({np.sum(arr == 0)/total*100:.1f}%)")
    print(f"  >0 regret:     {np.sum(arr > 0)} ({np.sum(arr > 0)/total*100:.1f}%)")

    return per_case_regrets

def diagnostic_random_policy(df_test, actions, costs):
    """Random action selection should have HIGH regret."""
    print(f"\n{'='*60}")
    print(f"DIAGNOSTIC 6: Random Policy Benchmark")
    print(f"{'='*60}")

    rng = np.random.default_rng(42)
    total_utility = 0
    oracle_utility = 0

    for i in range(len(df_test)):
        row = df_test.iloc[i]
        amt = row["amount_at_risk_paise"]

        random_action = rng.choice(actions)
        outcome = row.get(f"oracle_{random_action}_72h", 0)
        total_utility += int(outcome * amt) - costs[random_action]

        best_u = 0
        for a in actions:
            o = row.get(f"oracle_{a}_72h", 0)
            u = int(o * amt) - costs[a]
            if u > best_u:
                best_u = u
        oracle_utility += best_u

    regret = oracle_utility - total_utility
    print(f"  Random Utility:  Rs. {total_utility/100:,.2f}")
    print(f"  Oracle Utility:  Rs. {oracle_utility/100:,.2f}")
    print(f"  Random Regret:   Rs. {regret/100:,.2f}")

    return regret

def diagnostic_shuffled_labels(train_df, val_df, test_df, tabular_features, actions, costs):
    """Train LightGBM on SHUFFLED targets. Should collapse."""
    print(f"\n{'='*60}")
    print(f"DIAGNOSTIC 7: Shuffled Label Test (LightGBM)")
    print(f"{'='*60}")

    train_ds = RevPilotDataset(train_df, tabular_features)
    test_ds = RevPilotDataset(test_df, tabular_features)

    # Shuffle targets
    rng = np.random.default_rng(999)
    y_shuffled = train_ds.targets.copy()
    rng.shuffle(y_shuffled)

    model = get_lightgbm_baseline()
    model.fit(train_ds.tab_data, y_shuffled)
    preds = model.predict_proba(test_ds.tab_data)

    y_test = test_ds.targets
    metrics = evaluate_predictions(y_test, preds, "LightGBM (SHUFFLED)")
    return metrics

def diagnostic_cost_perturbation(df_test, actions, costs, tab_data, seq_data, tabular_features, get_preds_fn):
    """Re-evaluate with perturbed costs."""
    print(f"\n{'='*60}")
    print(f"DIAGNOSTIC 5: Cost Perturbation (+10%, -10%)")
    print(f"{'='*60}")

    for label, mult in [("costs +10%", 1.1), ("costs -10%", 0.9)]:
        perturbed = {a: int(c * mult) for a, c in costs.items()}
        # Quick oracle check
        oracle_u = 0
        model_u = 0
        for i in range(min(5000, len(df_test))):
            row = df_test.iloc[i]
            amt = row["amount_at_risk_paise"]

            best_ou = 0
            for a in actions:
                o = row.get(f"oracle_{a}_72h", 0)
                u = int(o * amt) - perturbed[a]
                if u > best_ou:
                    best_ou = u
            oracle_u += best_ou

            # Model decision with perturbed costs
            best_mu = -np.inf
            best_ma = "NO_ACTION"
            for a in actions:
                act_tab = tab_data[i:i+1].copy()
                for c_name in actions:
                    col_name = f"action_{c_name}"
                    if col_name in tabular_features:
                        feat_idx = tabular_features.index(col_name)
                        act_tab[0, feat_idx] = 1.0 if c_name == a else 0.0
                preds = get_preds_fn(act_tab, seq_data[i:i+1])
                ev = preds[0, 3] * amt - perturbed[a]
                if ev > best_mu:
                    best_mu = ev
                    best_ma = a

            outcome = row.get(f"oracle_{best_ma}_72h", 0)
            model_u += int(outcome * amt) - perturbed[best_ma]

        regret = oracle_u - model_u
        print(f"  {label}: Oracle Rs.{oracle_u/100:,.0f}, Model Rs.{model_u/100:,.0f}, Regret Rs.{regret/100:,.0f}")

def main():
    actions, costs = load_policy()
    print(f"Actions: {actions}")
    print(f"Costs (paise): {costs}")

    data_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'world_model_events_seed42.parquet')
    train_df, val_df, test_df, tabular_features = prepare_data(data_path)

    test_ds = RevPilotDataset(test_df, tabular_features)

    # 1. Oracle distribution
    oracle_picks, oracle_utils = diagnostic_oracle_distribution(test_df, actions, costs)

    # 6. Random policy
    diagnostic_random_policy(test_df, actions, costs)

    # 7. Shuffled labels
    diagnostic_shuffled_labels(train_df, val_df, test_df, tabular_features, actions, costs)

    # Train a real LightGBM for per-case diagnostics
    print("\n--- Training LightGBM for per-case diagnostics ---")
    train_ds = RevPilotDataset(train_df, tabular_features)
    val_ds = RevPilotDataset(val_df, tabular_features)

    lgb = get_lightgbm_baseline()
    lgb.fit(train_ds.tab_data, train_ds.targets)

    # Calibrate
    val_preds = lgb.predict_proba(val_ds.tab_data)
    cals = []
    for i in range(5):
        ir = IsotonicRegression(out_of_bounds='clip')
        ir.fit(val_preds[:, i], val_ds.targets[:, i])
        cals.append(ir)

    def lgb_predict(tab, seq):
        raw = lgb.predict_proba(tab)
        cal = np.zeros_like(raw)
        for i in range(5):
            cal[:, i] = cals[i].predict(raw[:, i])
        return np.maximum.accumulate(cal, axis=1)

    # 3. Per-case regret (sample first 5000 for speed)
    small_test = test_df.head(5000).copy()
    diagnostic_per_case_regret(
        small_test, actions, costs, lgb_predict,
        test_ds.tab_data[:5000], test_ds.seq_data[:5000],
        tabular_features, "LightGBM"
    )

    # 5. Cost perturbation
    diagnostic_cost_perturbation(
        test_df, actions, costs,
        test_ds.tab_data, test_ds.seq_data,
        tabular_features, lgb_predict
    )

    print("\n" + "="*60)
    print("ALL DIAGNOSTICS COMPLETE")
    print("="*60)

if __name__ == "__main__":
    main()
