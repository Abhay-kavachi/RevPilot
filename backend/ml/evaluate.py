import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss, log_loss
import warnings

def evaluate_predictions(y_true, y_pred_cdf, df_test, model_name="Model"):
    print(f"\n{'='*50}\nEvaluating {model_name}\n{'='*50}")
    horizons = ["1h", "6h", "24h", "72h", "168h"]
    
    print("--- Predictive Metrics ---")
    for i, h in enumerate(horizons):
        y_t = y_true[:, i]
        y_p = y_pred_cdf[:, i]
        try:
            auc = roc_auc_score(y_t, y_p)
            pr_auc = average_precision_score(y_t, y_p)
            brier = brier_score_loss(y_t, y_p)
            ll = log_loss(y_t, y_p)
            print(f"Horizon {h}: AUC={auc:.3f} | PR-AUC={pr_auc:.3f} | Brier={brier:.3f} | LogLoss={ll:.3f}")
        except ValueError:
            pass
            
def evaluate_policy_regret(df_test, tabular_features, tab_data, seq_data, get_preds_fn, model_name="Model"):
    print(f"\n--- Decision Quality & Regret ({model_name}) ---")
    
    actions_map = {"WAIT": 0, "EMAIL": 1, "SMS": 2, "WHATSAPP": 3, "CREATE_PAYMENT_LINK": 4, "RETRY_PAYMENT_OPPORTUNITY": 5}
    action_costs = {"WAIT": 0, "EMAIL": 5, "SMS": 15, "WHATSAPP": 25, "CREATE_PAYMENT_LINK": 50, "RETRY_PAYMENT_OPPORTUNITY": 200}
    
    amounts = df_test["amount_at_risk"].values / 100 # converting paise to rupees for easier reading
    num_cases = len(df_test)
    
    # We will score ALL actions for ALL cases in one go.
    # We create a batched tensor for each action.
    all_preds = {} # action -> preds (N, 5)
    
    for act_name, act_idx in actions_map.items():
        # Copy tabular data and override the action one-hot encoding
        act_tab = tab_data.copy()
        for c_name, c_idx in actions_map.items():
            feat_idx = tabular_features.index(f"action_{c_name}")
            act_tab[:, feat_idx] = 1.0 if c_name == act_name else 0.0
            
        # The sequence data is pre-action context, so it remains UNCHANGED!
        # The model predicts P(recovery | action, pre-action context).
        
        preds = get_preds_fn(act_tab, seq_data)
        all_preds[act_name] = preds[:, 3] # Horizon 72h is index 3
        
    # Now compute Expected Value (EV) for each action
    # EV = P(success)*Amount - Cost
    ev_matrix = np.zeros((num_cases, len(actions_map)))
    
    for j, (act_name, cost) in enumerate(action_costs.items()):
        p_succ = all_preds[act_name]
        ev_matrix[:, j] = p_succ * amounts - cost
        
    # Best Action according to Strategy
    best_action_idx = np.argmax(ev_matrix, axis=1)
    
    # Map index back to names
    act_names = list(action_costs.keys())
    
    # Calculate Strategy Realized Utility
    # We check the HIDDEN potential outcomes in df_test!
    # df_test has 'oracle_{ACTION}_72h'
    strategy_utility = 0
    oracle_utility = 0
    
    # For MAX_RETRY Baseline (always pick RETRY)
    max_retry_utility = 0
    
    for i in range(num_cases):
        best_act = act_names[best_action_idx[i]]
        cost = action_costs[best_act]
        
        # Did the chosen action actually succeed?
        outcome = df_test.iloc[i][f"oracle_{best_act}_72h"]
        utility = outcome * amounts[i] - cost
        strategy_utility += utility
        
        # What was the ORACLE best action?
        best_oracle_u = -np.inf
        for a_name, a_cost in action_costs.items():
            o = df_test.iloc[i][f"oracle_{a_name}_72h"]
            u = o * amounts[i] - a_cost
            if u > best_oracle_u:
                best_oracle_u = u
                
        oracle_utility += max(best_oracle_u, 0) # assume wait = 0 utility lower bound
        
        # MAX RETRY Baseline
        mr_o = df_test.iloc[i]["oracle_RETRY_PAYMENT_OPPORTUNITY_72h"]
        max_retry_utility += mr_o * amounts[i] - 200
        
    regret = oracle_utility - strategy_utility
    print(f"Oracle Utility:       Rs. {oracle_utility:,.2f}")
    print(f"MAX_RETRY Utility:    Rs. {max_retry_utility:,.2f}")
    print(f"{model_name} Utility: Rs. {strategy_utility:,.2f}")
    print(f"-> {model_name} Regret: Rs. {regret:,.2f}")
    
    return regret
