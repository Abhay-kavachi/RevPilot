import os
import sys
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from sklearn.isotonic import IsotonicRegression

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app.core.policy import PolicyManager
from dataset import prepare_data, RevPilotDataset
from models import HybridModel, get_lightgbm_baseline

def _load_policy():
    pm = PolicyManager()
    return list(pm.economic_policy.action_costs_paise.keys()), pm.economic_policy.action_costs_paise

def train_lightgbm(X_train, y_train):
    model = get_lightgbm_baseline()
    model.models = [model.models[i].__class__(n_estimators=100, learning_rate=0.05, n_jobs=-1, random_state=42) for i in range(5)]
    model.fit(X_train, y_train)
    return model

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

def train_hybrid(train_loader, val_loader, n_tab, n_seq, seed=42):
    torch.manual_seed(seed)
    np.random.seed(seed)
    model = HybridModel(tab_features=n_tab, seq_features=n_seq)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    criterion = nn.BCELoss()
    for epoch in range(5): # EPOCHS_NN = 5
        model.train()
        for batch in train_loader:
            tab_x, seq_x, targets = batch[0], batch[1], batch[2]
            optimizer.zero_grad()
            preds = model(tab_x, seq_x)
            loss = criterion(preds, targets)
            loss.backward()
            optimizer.step()
    return model

def calibrate_nn(model, val_loader):
    model.eval()
    preds_list, targets_list = [], []
    with torch.no_grad():
        for batch in val_loader:
            preds_list.append(model(batch[0], batch[1]).numpy())
            targets_list.append(batch[2].numpy())
    preds_all = np.concatenate(preds_list)
    targets_all = np.concatenate(targets_list)
    calibrators = []
    for i in range(5):
        ir = IsotonicRegression(out_of_bounds='clip')
        ir.fit(preds_all[:, i], targets_all[:, i])
        calibrators.append(ir)
    return calibrators

def predict_calibrated_nn(model, calibrators, tab_data, seq_data):
    model.eval()
    with torch.no_grad():
        raw = model(torch.tensor(tab_data), torch.tensor(seq_data)).numpy()
    cal = np.zeros_like(raw)
    for i in range(5):
        cal[:, i] = calibrators[i].predict(raw[:, i])
    return np.maximum.accumulate(cal, axis=1)

def get_case_utilities(preds, df, actions, costs):
    # Matches evaluate.py exactly
    amt_paise = df['amount_at_risk_paise'].values
    horizon = "72h" # Evaluation horizon
    
    n_cases = len(df)
    utilities = np.zeros(n_cases)
    
    for i in range(n_cases):
        evs = []
        for j, a in enumerate(actions):
            if a == 'NO_ACTION':
                ev = -costs[a]
            else:
                prob = preds[i, 3] # 72h is index 3
                ev = (prob * amt_paise[i]) - costs[a]
            evs.append(ev)
        best_idx = np.argmax(evs)
        best_act = actions[best_idx]
        
        # Realized outcome from hidden oracle
        oracle_col = f"oracle_{best_act}_{horizon}"
        outcome = df.iloc[i].get(oracle_col, 0)
        actual_utility = int(outcome * amt_paise[i]) - costs[best_act]
        
        utilities[i] = actual_utility
        
    return utilities

def bootstrap_ci(diff_array, num_samples=10000, alpha=0.05):
    n = len(diff_array)
    means = np.zeros(num_samples)
    for i in range(num_samples):
        sample = np.random.choice(diff_array, size=n, replace=True)
        means[i] = np.mean(sample)
    lower = np.percentile(means, 100 * (alpha / 2))
    upper = np.percentile(means, 100 * (1 - alpha / 2))
    return lower, upper

def main():
    actions, costs = _load_policy()
    data_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'world_model_events_seed42.parquet')
    train_df, val_df, test_df, tabular_features = prepare_data(data_path)

    train_ds = RevPilotDataset(train_df, tabular_features)
    val_ds = RevPilotDataset(val_df, tabular_features)
    test_ds = RevPilotDataset(test_df, tabular_features)
    
    g = torch.Generator()
    g.manual_seed(42)
    train_loader = DataLoader(train_ds, batch_size=256, shuffle=True, generator=g)
    val_loader = DataLoader(val_ds, batch_size=256)

    n_tab = len(tabular_features)
    n_seq = 4
    
    print("Training LightGBM (Seed 42)...")
    lgb_model = train_lightgbm(train_ds.tab_data, train_ds.targets)
    lgb_cals = calibrate_sklearn(lgb_model, val_ds.tab_data, val_ds.targets)
    lgb_preds = predict_calibrated_sklearn(lgb_model, lgb_cals, test_ds.tab_data)
    
    print("Training Hybrid (Seed 42)...")
    hyb_model = train_hybrid(train_loader, val_loader, n_tab, n_seq, 42)
    hyb_cals = calibrate_nn(hyb_model, val_loader)
    hyb_preds = predict_calibrated_nn(hyb_model, hyb_cals, test_ds.tab_data, test_ds.seq_data)
    
    print("Calculating Case-Level Utilities...")
    u_lgb = get_case_utilities(lgb_preds, test_df, actions, costs)
    u_hyb = get_case_utilities(hyb_preds, test_df, actions, costs)
    
    diff = u_hyb - u_lgb
    
    print("\n==================================================")
    print("1. PAIRED MODEL COMPARISON (TEST CASES N=63731)")
    print("==================================================")
    mean_diff = np.mean(diff)
    median_diff = np.median(diff)
    std_diff = np.std(diff)
    
    print(f"Mean Difference (Hybrid - LightGBM): Rs. {mean_diff/100:.6f} / case")
    print(f"Median Difference: Rs. {median_diff/100:.6f} / case")
    print(f"Standard Deviation: Rs. {std_diff/100:.6f}")
    
    print("Running Paired Bootstrap (10,000 samples)...")
    lower, upper = bootstrap_ci(diff)
    print(f"95% Bootstrap CI for Mean Difference: [Rs. {lower/100:.6f}, Rs. {upper/100:.6f}]")
    
    hyb_better = np.sum(diff > 0)
    lgb_better = np.sum(diff < 0)
    ties = np.sum(diff == 0)
    n = len(diff)
    
    print(f"Cases Hybrid > LightGBM: {hyb_better} ({(hyb_better/n)*100:.2f}%)")
    print(f"Cases LightGBM > Hybrid: {lgb_better} ({(lgb_better/n)*100:.2f}%)")
    print(f"Cases Tied (Exact):      {ties} ({(ties/n)*100:.2f}%)")
    
    total_diff = np.sum(diff)
    print(f"Exact Total Utility Difference (Hybrid - LightGBM): Rs. {total_diff/100:.2f}")
    
    print("\n==================================================")
    print("3. SPEED CLAIM CALIBRATION")
    print("==================================================")
    print("Batch size measured: 63,731 predictions")
    
if __name__ == "__main__":
    main()
