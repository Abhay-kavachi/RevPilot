"""
RevPilot ML Evaluation Module.

All monetary calculations use INTEGER PAISE internally.
Human-readable output converts to rupees at the final print step only.

The evaluator loads action costs from the REAL EconomicPolicy (policy.json).
No duplicated cost dictionaries anywhere.
"""
import numpy as np
import pandas as pd
import sys, os
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss, log_loss

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app.core.policy import PolicyManager

def _load_policy():
    pm = PolicyManager()
    actions = list(pm.economic_policy.action_costs_paise.keys())
    costs_paise = pm.economic_policy.action_costs_paise
    return actions, costs_paise

def evaluate_predictions(y_true, y_pred_cdf, model_name="Model"):
    """Evaluate predictive quality metrics on out-of-time test set."""
    print(f"\n{'='*60}")
    print(f"Predictive Metrics: {model_name}")
    print(f"{'='*60}")
    horizons = ["1h", "6h", "24h", "72h", "168h"]
    results = {}
    for i, h in enumerate(horizons):
        y_t = y_true[:, i]
        y_p = np.clip(y_pred_cdf[:, i], 1e-7, 1 - 1e-7)
        try:
            auc = roc_auc_score(y_t, y_p)
            pr_auc = average_precision_score(y_t, y_p)
            brier = brier_score_loss(y_t, y_p)
            ll = log_loss(y_t, y_p)
            print(f"  {h}: AUC={auc:.4f} | PR-AUC={pr_auc:.4f} | Brier={brier:.4f} | LogLoss={ll:.4f}")
            results[h] = {"auc": auc, "pr_auc": pr_auc, "brier": brier, "logloss": ll}
        except ValueError:
            print(f"  {h}: SKIPPED (single class)")
    return results

def evaluate_policy_regret(df_test, actions_list, tab_data, seq_data, tabular_features, get_preds_fn, model_name="Model", horizon_idx=3):
    """
    Evaluate decision quality and regret against the Oracle.

    All utility arithmetic is in INTEGER PAISE.
    Final display converts to rupees.

    Args:
        df_test: test DataFrame with oracle columns and amount_at_risk_paise
        actions_list: canonical action list from policy.json
        tab_data: (N, F) numpy array of tabular features
        seq_data: (N, S, 4) numpy array of sequence features
        tabular_features: list of tabular feature names
        get_preds_fn: callable(tab, seq) -> (N, 5) probability CDF
        model_name: display name
        horizon_idx: which horizon column to use for decisions (default 3 = 72h)
    """
    _, costs_paise = _load_policy()

    print(f"\n{'='*60}")
    print(f"Decision Quality & Regret: {model_name}")
    print(f"{'='*60}")

    amounts_paise = df_test["amount_at_risk_paise"].values  # integer paise
    num_cases = len(df_test)

    # Score ALL actions for ALL cases
    all_preds = {}
    for act_name in actions_list:
        act_tab = tab_data.copy()
        for c_name in actions_list:
            col_name = f"action_{c_name}"
            if col_name in tabular_features:
                feat_idx = tabular_features.index(col_name)
                act_tab[:, feat_idx] = 1.0 if c_name == act_name else 0.0

        preds = get_preds_fn(act_tab, seq_data)
        all_preds[act_name] = preds[:, horizon_idx]

    # EV = P(success) * amount_paise - cost_paise  (all paise)
    ev_matrix = np.zeros((num_cases, len(actions_list)))
    for j, act_name in enumerate(actions_list):
        cost = costs_paise[act_name]  # integer paise from policy
        ev_matrix[:, j] = all_preds[act_name] * amounts_paise - cost

    best_action_idx = np.argmax(ev_matrix, axis=1)

    # Compute utilities
    strategy_utility_paise = 0
    oracle_utility_paise = 0
    max_retry_utility_paise = 0
    unnecessary_interventions = 0
    correct_vs_oracle = 0
    total_actions = 0

    # Find the retry action name
    retry_action = "RETRY_PAYMENT" if "RETRY_PAYMENT" in actions_list else actions_list[-1]
    retry_cost = costs_paise.get(retry_action, 0)

    for i in range(num_cases):
        best_act = actions_list[best_action_idx[i]]
        cost = costs_paise[best_act]

        # Realized outcome from hidden oracle
        oracle_col = f"oracle_{best_act}_72h"
        outcome = df_test.iloc[i].get(oracle_col, 0)
        utility = int(outcome * amounts_paise[i]) - cost
        strategy_utility_paise += utility
        total_actions += 1

        if best_act != "NO_ACTION" and outcome == 0:
            unnecessary_interventions += 1

        # Oracle best
        best_oracle_u = 0  # NO_ACTION baseline = 0
        best_oracle_act = "NO_ACTION"
        for a_name in actions_list:
            a_cost = costs_paise[a_name]
            o = df_test.iloc[i].get(f"oracle_{a_name}_72h", 0)
            u = int(o * amounts_paise[i]) - a_cost
            if u > best_oracle_u:
                best_oracle_u = u
                best_oracle_act = a_name
        oracle_utility_paise += best_oracle_u

        if best_act == best_oracle_act:
            correct_vs_oracle += 1

        # MAX_RETRY baseline
        mr_o = df_test.iloc[i].get(f"oracle_{retry_action}_72h", 0)
        max_retry_utility_paise += int(mr_o * amounts_paise[i]) - retry_cost

    regret_paise = oracle_utility_paise - strategy_utility_paise
    action_accuracy = correct_vs_oracle / num_cases if num_cases > 0 else 0

    # Convert to rupees for display only
    print(f"  Oracle Utility:       Rs. {oracle_utility_paise / 100:,.2f}")
    print(f"  MAX_RETRY Utility:    Rs. {max_retry_utility_paise / 100:,.2f}")
    print(f"  {model_name} Utility: Rs. {strategy_utility_paise / 100:,.2f}")
    print(f"  Regret:               Rs. {regret_paise / 100:,.2f}")
    print(f"  Action accuracy vs Oracle: {action_accuracy:.4f}")
    print(f"  Unnecessary interventions: {unnecessary_interventions}/{num_cases}")
    print(f"  Avg actions/case: {total_actions / num_cases:.2f}")

    return {
        "oracle_paise": oracle_utility_paise,
        "strategy_paise": strategy_utility_paise,
        "max_retry_paise": max_retry_utility_paise,
        "regret_paise": regret_paise,
        "action_accuracy": action_accuracy,
        "unnecessary_interventions": unnecessary_interventions,
    }
