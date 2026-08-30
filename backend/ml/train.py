"""
RevPilot ML Multi-Seed Training & Evaluation Pipeline.

Trains and compares ALL required models across multiple seeds:
  A. Logistic Regression
  B. LightGBM
  C. Standalone GRU
  D. Hybrid GRU + Tabular
  E. Compact Transformer Challenger

Decision regret against Oracle counterfactual world.
"""
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
import numpy as np
import json
import os
import sys
import time
from sklearn.isotonic import IsotonicRegression
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app.core.policy import PolicyManager
from dataset import prepare_data, RevPilotDataset
from models import (
    TemporalGRU, CompactTransformer, HybridModel,
    get_logistic_baseline, get_lightgbm_baseline,
)
from evaluate import evaluate_predictions, evaluate_policy_regret

SEEDS = [42, 123, 2024]
EPOCHS_NN = 5

def _load_actions():
    pm = PolicyManager()
    return list(pm.economic_policy.action_costs_paise.keys())

def calibrate_sklearn(model, X_val, y_val):
    raw_preds = model.predict_proba(X_val)
    calibrators = []
    for i in range(5):
        ir = IsotonicRegression(out_of_bounds='clip')
        ir.fit(raw_preds[:, i], y_val[:, i])
        calibrators.append(ir)
    return calibrators

def predict_calibrated_sklearn(model, calibrators, X):
    raw = model.predict_proba(X)
    cal = np.zeros_like(raw)
    for i in range(5):
        cal[:, i] = calibrators[i].predict(raw[:, i])
    return np.maximum.accumulate(cal, axis=1)

def calibrate_nn(model, val_loader):
    model.eval()
    preds_list, targets_list = [], []
    with torch.no_grad():
        for batch in val_loader:
            tab_x, seq_x, targets = batch[0], batch[1], batch[2]
            if hasattr(model, 'tab_mlp'):
                preds = model(tab_x, seq_x)
            else:
                preds = model(seq_x)
            preds_list.append(preds.numpy())
            targets_list.append(targets.numpy())
    preds_all = np.concatenate(preds_list)
    targets_all = np.concatenate(targets_list)

    calibrators = []
    for i in range(5):
        ir = IsotonicRegression(out_of_bounds='clip')
        ir.fit(preds_all[:, i], targets_all[:, i])
        calibrators.append(ir)
    return calibrators

def predict_calibrated_nn(model, calibrators, tab_data, seq_data, is_hybrid=True):
    model.eval()
    with torch.no_grad():
        if is_hybrid:
            raw = model(torch.tensor(tab_data), torch.tensor(seq_data)).numpy()
        else:
            raw = model(torch.tensor(seq_data)).numpy()
    cal = np.zeros_like(raw)
    for i in range(5):
        cal[:, i] = calibrators[i].predict(raw[:, i])
    return np.maximum.accumulate(cal, axis=1)

def train_nn(model, train_loader, val_loader, epochs, seed, is_hybrid=True):
    torch.manual_seed(seed)
    np.random.seed(seed)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    criterion = nn.BCELoss()
    for epoch in range(epochs):
        model.train()
        for batch in train_loader:
            tab_x, seq_x, targets = batch[0], batch[1], batch[2]
            optimizer.zero_grad()
            if is_hybrid:
                preds = model(tab_x, seq_x)
            else:
                preds = model(seq_x)
            loss = criterion(preds, targets)
            loss.backward()
            optimizer.step()

def evaluate_model_pipeline(model_type, seed, train_ds, val_ds, test_ds, test_df, actions, tabular_features, n_tab, n_seq):
    import random
    random.seed(seed)
    torch.manual_seed(seed)
    np.random.seed(seed)
    
    # Create strictly seeded dataloaders
    g = torch.Generator()
    g.manual_seed(seed)
    train_loader = DataLoader(train_ds, batch_size=256, shuffle=True, generator=g)
    val_loader = DataLoader(val_ds, batch_size=256)
    
    X_train, y_train = train_ds.tab_data, train_ds.targets
    X_val, y_val = val_ds.tab_data, val_ds.targets
    X_test, y_test = test_ds.tab_data, test_ds.targets
    
    t0 = time.time()
    
    if model_type == "Logistic":
        model = get_logistic_baseline()
        model.fit(X_train, y_train)
        cals = calibrate_sklearn(model, X_val, y_val)
        
        t1 = time.time()
        preds = predict_calibrated_sklearn(model, cals, X_test)
        inference_time = (time.time() - t1) * 1000  # ms
        
        def pred_fn(t, s): return predict_calibrated_sklearn(model, cals, t)
        
    elif model_type == "LightGBM":
        model = get_lightgbm_baseline()
        model.models = [model.models[i].__class__(n_estimators=100, learning_rate=0.05, n_jobs=-1, random_state=seed) for i in range(5)]
        model.fit(X_train, y_train)
        cals = calibrate_sklearn(model, X_val, y_val)
        
        t1 = time.time()
        preds = predict_calibrated_sklearn(model, cals, X_test)
        inference_time = (time.time() - t1) * 1000
        
        def pred_fn(t, s): return predict_calibrated_sklearn(model, cals, t)
        
    elif model_type == "GRU":
        model = TemporalGRU(seq_features=n_seq, hidden_dim=64, num_horizons=5)
        train_nn(model, train_loader, val_loader, EPOCHS_NN, seed, False)
        cals = calibrate_nn(model, val_loader)
        
        t1 = time.time()
        preds = predict_calibrated_nn(model, cals, X_test, test_ds.seq_data, False)
        inference_time = (time.time() - t1) * 1000
        
        def pred_fn(t, s): return predict_calibrated_nn(model, cals, t, s, False)
        
    elif model_type == "Hybrid":
        model = HybridModel(tab_features=n_tab, seq_features=n_seq)
        train_nn(model, train_loader, val_loader, EPOCHS_NN, seed, True)
        cals = calibrate_nn(model, val_loader)
        
        t1 = time.time()
        preds = predict_calibrated_nn(model, cals, X_test, test_ds.seq_data, True)
        inference_time = (time.time() - t1) * 1000
        
        def pred_fn(t, s): return predict_calibrated_nn(model, cals, t, s, True)
        
    elif model_type == "Transformer":
        model = CompactTransformer(seq_features=n_seq, hidden_dim=64, num_heads=4, num_layers=1, num_horizons=5)
        train_nn(model, train_loader, val_loader, EPOCHS_NN, seed, False)
        cals = calibrate_nn(model, val_loader)
        
        t1 = time.time()
        preds = predict_calibrated_nn(model, cals, X_test, test_ds.seq_data, False)
        inference_time = (time.time() - t1) * 1000
        
        def pred_fn(t, s): return predict_calibrated_nn(model, cals, t, s, False)

    # Calculate metrics silently
    horizons = ["1h", "6h", "24h", "72h", "168h"]
    y_t = y_test[:, 3] # 72h
    y_p = np.clip(preds[:, 3], 1e-7, 1 - 1e-7)
    
    from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss, log_loss
    auc = roc_auc_score(y_t, y_p)
    pr_auc = average_precision_score(y_t, y_p)
    brier = brier_score_loss(y_t, y_p)
    ll = log_loss(y_t, y_p)
    
    # Supress print by replacing evaluate_policy_regret internally or just keeping output
    import io
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    regret_dict = evaluate_policy_regret(
        test_df, actions, X_test, test_ds.seq_data, tabular_features,
        pred_fn, model_type
    )
    sys.stdout = old_stdout
    
    num_cases = len(test_df)
    regret_per_case = regret_dict["regret_paise"] / num_cases
    
    return {
        "auc_72h": auc,
        "pr_auc_72h": pr_auc,
        "brier_72h": brier,
        "logloss_72h": ll,
        "total_utility_paise": regret_dict["strategy_paise"],
        "regret_paise": regret_dict["regret_paise"],
        "regret_per_case_paise": regret_per_case,
        "agreement": regret_dict["action_accuracy"],
        "unnecessary": regret_dict["unnecessary_interventions"],
        "inference_ms": inference_time
    }

def main():
    actions = _load_actions()
    data_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'world_model_events_seed42.parquet')
    train_df, val_df, test_df, tabular_features = prepare_data(data_path)

    train_ds = RevPilotDataset(train_df, tabular_features)
    val_ds = RevPilotDataset(val_df, tabular_features)
    test_ds = RevPilotDataset(test_df, tabular_features)
    n_tab = len(tabular_features)
    n_seq = 4

    models = ["Logistic", "LightGBM", "GRU", "Hybrid", "Transformer"]
    
    results = defaultdict(lambda: defaultdict(list))
    
    print("\nStarting Multi-Seed Benchmark...")
    for seed in SEEDS:
        print(f"\n--- SEED {seed} ---")
        for m in models:
            print(f"Training {m}...")
            res = evaluate_model_pipeline(m, seed, train_ds, val_ds, test_ds, test_df, actions, tabular_features, n_tab, n_seq)
            for k, v in res.items():
                results[m][k].append(v)
                
    # Aggregate
    final_stats = {}
    print("\n" + "="*80)
    print("FINAL MULTI-SEED RESULTS (Mean ± Std)")
    print("="*80)
    for m in models:
        final_stats[m] = {}
        print(f"\nModel: {m}")
        for k in results[m].keys():
            arr = np.array(results[m][k])
            mean_val = np.mean(arr)
            std_val = np.std(arr)
            final_stats[m][k] = {
                "mean": mean_val,
                "std": std_val,
                "min": float(np.min(arr)),
                "max": float(np.max(arr)),
                "raw": arr.tolist()
            }
            
            if "paise" in k:
                # print in rupees
                print(f"  {k}: Rs. {mean_val/100:,.2f} ± Rs. {std_val/100:,.2f}")
            elif "inference" in k:
                print(f"  {k}: {mean_val:,.1f} ms ± {std_val:,.1f} ms")
            else:
                print(f"  {k}: {mean_val:.4f} ± {std_val:.4f}")
                
    os.makedirs("data", exist_ok=True)
    with open("data/model_comparison_results.json", "w") as f:
        json.dump(final_stats, f, indent=2)

if __name__ == "__main__":
    main()
