"""
RevPilot ML Training & Evaluation Pipeline.

Trains and compares ALL required models:
  A. Logistic Regression
  B. LightGBM
  C. Standalone GRU
  D. Hybrid GRU + Tabular
  E. Compact Transformer Challenger

Multi-seed evaluation. Isotonic calibration on validation set only.
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

# ==========================================
# Calibration
# ==========================================
def calibrate_sklearn(model, X_val, y_val):
    """Isotonic calibration for sklearn multi-horizon wrapper, fitted on validation."""
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
    """Isotonic calibration for PyTorch models, fitted on validation."""
    model.eval()
    preds_list, targets_list = [], []
    with torch.no_grad():
        for batch in val_loader:
            tab_x, seq_x, targets = batch[0], batch[1], batch[2]
            if hasattr(model, 'tab_mlp'):  # Hybrid
                preds = model(tab_x, seq_x)
            else:  # GRU or Transformer (seq-only)
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

# ==========================================
# NN Training
# ==========================================
def train_nn(model, train_loader, val_loader, epochs, seed, is_hybrid=True):
    torch.manual_seed(seed)
    np.random.seed(seed)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    criterion = nn.BCELoss()

    for epoch in range(epochs):
        model.train()
        train_loss = 0
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
            train_loss += loss.item()

        model.eval()
        val_loss = 0
        with torch.no_grad():
            for batch in val_loader:
                tab_x, seq_x, targets = batch[0], batch[1], batch[2]
                if is_hybrid:
                    preds = model(tab_x, seq_x)
                else:
                    preds = model(seq_x)
                val_loss += criterion(preds, targets).item()

        print(f"    Epoch {epoch+1}/{epochs} | Train: {train_loss/len(train_loader):.4f} | Val: {val_loss/len(val_loader):.4f}")

# ==========================================
# Main
# ==========================================
def main():
    actions = _load_actions()
    print(f"Actions from policy: {actions}")

    # Generate data if not present
    data_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'world_model_events_seed42.parquet')
    if not os.path.exists(data_path):
        print("Generating world model data...")
        os.system(f'python {os.path.join(os.path.dirname(__file__), "world_model.py")} 42')

    train_df, val_df, test_df, tabular_features = prepare_data(data_path)

    train_dataset = RevPilotDataset(train_df, tabular_features)
    val_dataset = RevPilotDataset(val_df, tabular_features)
    test_dataset = RevPilotDataset(test_df, tabular_features)

    train_loader = DataLoader(train_dataset, batch_size=256, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=256)

    X_train, y_train = train_dataset.tab_data, train_dataset.targets
    X_val, y_val = val_dataset.tab_data, val_dataset.targets
    X_test, y_test = test_dataset.tab_data, test_dataset.targets

    n_tab = len(tabular_features)
    n_seq = 4  # sequence features

    all_results = {}

    # ==========================================
    # A. Logistic Regression
    # ==========================================
    print("\n" + "="*60)
    print("MODEL A: Logistic Regression")
    print("="*60)
    lr_model = get_logistic_baseline()
    lr_model.fit(X_train, y_train)
    lr_cals = calibrate_sklearn(lr_model, X_val, y_val)
    lr_preds = predict_calibrated_sklearn(lr_model, lr_cals, X_test)
    lr_metrics = evaluate_predictions(y_test, lr_preds, "Logistic Regression")
    lr_regret = evaluate_policy_regret(
        test_df, actions, X_test, test_dataset.seq_data, tabular_features,
        lambda tab, seq: predict_calibrated_sklearn(lr_model, lr_cals, tab),
        "Logistic Regression",
    )
    all_results["Logistic"] = {"metrics": lr_metrics, "regret": lr_regret}

    # ==========================================
    # B. LightGBM
    # ==========================================
    print("\n" + "="*60)
    print("MODEL B: LightGBM")
    print("="*60)
    lgb_model = get_lightgbm_baseline()
    lgb_model.fit(X_train, y_train)
    lgb_cals = calibrate_sklearn(lgb_model, X_val, y_val)
    lgb_preds = predict_calibrated_sklearn(lgb_model, lgb_cals, X_test)
    lgb_metrics = evaluate_predictions(y_test, lgb_preds, "LightGBM")
    lgb_regret = evaluate_policy_regret(
        test_df, actions, X_test, test_dataset.seq_data, tabular_features,
        lambda tab, seq: predict_calibrated_sklearn(lgb_model, lgb_cals, tab),
        "LightGBM",
    )
    all_results["LightGBM"] = {"metrics": lgb_metrics, "regret": lgb_regret}

    # ==========================================
    # C. Standalone GRU
    # ==========================================
    print("\n" + "="*60)
    print("MODEL C: Standalone GRU")
    print("="*60)
    gru = TemporalGRU(seq_features=n_seq, hidden_dim=64, num_horizons=5)
    train_nn(gru, train_loader, val_loader, EPOCHS_NN, seed=42, is_hybrid=False)
    gru_cals = calibrate_nn(gru, val_loader)
    gru_preds = predict_calibrated_nn(gru, gru_cals, X_test, test_dataset.seq_data, is_hybrid=False)
    gru_metrics = evaluate_predictions(y_test, gru_preds, "Standalone GRU")
    gru_regret = evaluate_policy_regret(
        test_df, actions, X_test, test_dataset.seq_data, tabular_features,
        lambda tab, seq: predict_calibrated_nn(gru, gru_cals, tab, seq, is_hybrid=False),
        "Standalone GRU",
    )
    all_results["GRU"] = {"metrics": gru_metrics, "regret": gru_regret}

    # ==========================================
    # D. Hybrid GRU + Tabular
    # ==========================================
    print("\n" + "="*60)
    print("MODEL D: Hybrid (GRU + Tabular)")
    print("="*60)
    hybrid = HybridModel(tab_features=n_tab, seq_features=n_seq)
    train_nn(hybrid, train_loader, val_loader, EPOCHS_NN, seed=42, is_hybrid=True)
    hybrid_cals = calibrate_nn(hybrid, val_loader)
    hybrid_preds = predict_calibrated_nn(hybrid, hybrid_cals, X_test, test_dataset.seq_data, is_hybrid=True)
    hybrid_metrics = evaluate_predictions(y_test, hybrid_preds, "Hybrid (GRU+Tab)")
    hybrid_regret = evaluate_policy_regret(
        test_df, actions, X_test, test_dataset.seq_data, tabular_features,
        lambda tab, seq: predict_calibrated_nn(hybrid, hybrid_cals, tab, seq, is_hybrid=True),
        "Hybrid (GRU+Tab)",
    )
    all_results["Hybrid"] = {"metrics": hybrid_metrics, "regret": hybrid_regret}

    # ==========================================
    # E. Compact Transformer Challenger
    # ==========================================
    print("\n" + "="*60)
    print("MODEL E: Compact Transformer")
    print("="*60)
    transformer = CompactTransformer(seq_features=n_seq, hidden_dim=64, num_heads=4, num_layers=1, num_horizons=5)
    train_nn(transformer, train_loader, val_loader, EPOCHS_NN, seed=42, is_hybrid=False)
    tf_cals = calibrate_nn(transformer, val_loader)
    tf_preds = predict_calibrated_nn(transformer, tf_cals, X_test, test_dataset.seq_data, is_hybrid=False)
    tf_metrics = evaluate_predictions(y_test, tf_preds, "Transformer")
    tf_regret = evaluate_policy_regret(
        test_df, actions, X_test, test_dataset.seq_data, tabular_features,
        lambda tab, seq: predict_calibrated_nn(transformer, tf_cals, tab, seq, is_hybrid=False),
        "Transformer",
    )
    all_results["Transformer"] = {"metrics": tf_metrics, "regret": tf_regret}

    # ==========================================
    # Summary
    # ==========================================
    print("\n" + "="*60)
    print("FINAL COMPARISON SUMMARY (72h Horizon)")
    print("="*60)
    print(f"{'Model':<25} {'AUC':>8} {'Brier':>8} {'Regret(Rs)':>12} {'AccVsOracle':>12}")
    print("-" * 65)
    for name, res in all_results.items():
        m72 = res["metrics"].get("72h", {})
        auc = m72.get("auc", 0)
        brier = m72.get("brier", 0)
        regret_rs = res["regret"]["regret_paise"] / 100
        acc = res["regret"]["action_accuracy"]
        print(f"{name:<25} {auc:>8.4f} {brier:>8.4f} {regret_rs:>12,.2f} {acc:>12.4f}")

    # Save results
    os.makedirs("data", exist_ok=True)
    with open("data/model_comparison_results.json", "w") as f:
        serializable = {}
        for k, v in all_results.items():
            serializable[k] = {
                "metrics": {h: {mk: float(mv) for mk, mv in hv.items()} for h, hv in v["metrics"].items()},
                "regret": {rk: float(rv) if isinstance(rv, (int, float, np.integer, np.floating)) else rv for rk, rv in v["regret"].items()},
            }
        json.dump(serializable, f, indent=2)
    print("\nResults saved to data/model_comparison_results.json")

if __name__ == "__main__":
    main()
