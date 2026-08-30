import torch
import torch.nn as nn
from torch.utils.data import DataLoader
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.isotonic import IsotonicRegression

from dataset import prepare_data, RevPilotDataset
from models import HybridModel, get_logistic_baseline, get_lightgbm_baseline
from evaluate import evaluate_predictions, evaluate_policy_regret

def train_nn(model, train_loader, val_loader, epochs=5, seed=42):
    torch.manual_seed(seed)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    criterion = nn.BCELoss()
    
    print(f"Training PyTorch NN (Seed {seed})...")
    for epoch in range(epochs):
        model.train()
        train_loss = 0
        for tab_x, seq_x, targets in train_loader:
            optimizer.zero_grad()
            preds = model(tab_x, seq_x)
            loss = criterion(preds, targets)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()
            
        model.eval()
        val_loss = 0
        with torch.no_grad():
            for tab_x, seq_x, targets in val_loader:
                preds = model(tab_x, seq_x)
                val_loss += criterion(preds, targets).item()
                
        print(f"Epoch {epoch+1} | Train Loss: {train_loss/len(train_loader):.4f} | Val Loss: {val_loss/len(val_loader):.4f}")

def calibrate_nn(model, val_loader):
    model.eval()
    val_preds = []
    val_targets = []
    with torch.no_grad():
        for tab_x, seq_x, targets in val_loader:
            preds = model(tab_x, seq_x)
            val_preds.append(preds.numpy())
            val_targets.append(targets.numpy())
            
    val_preds = np.concatenate(val_preds, axis=0)
    val_targets = np.concatenate(val_targets, axis=0)
    
    calibrators = []
    for i in range(5):
        ir = IsotonicRegression(out_of_bounds='clip')
        ir.fit(val_preds[:, i], val_targets[:, i])
        calibrators.append(ir)
    return calibrators

def predict_nn(model, tab_data, seq_data, calibrators=None):
    model.eval()
    with torch.no_grad():
        preds = model(torch.tensor(tab_data), torch.tensor(seq_data)).numpy()
        
    if calibrators is not None:
        cal_preds = np.zeros_like(preds)
        for i in range(5):
            cal_preds[:, i] = calibrators[i].predict(preds[:, i])
        # Enforce monotonicity
        preds = np.maximum.accumulate(cal_preds, axis=1)
    return preds

def main():
    train_df, val_df, test_df, tabular_features, full_df = prepare_data()
    
    train_dataset = RevPilotDataset(train_df, tabular_features)
    val_dataset = RevPilotDataset(val_df, tabular_features)
    test_dataset = RevPilotDataset(test_df, tabular_features)
    
    train_loader = DataLoader(train_dataset, batch_size=256, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=256)
    
    print("\n--- Training LightGBM Baseline ---")
    X_train = train_dataset.tab_data
    y_train = train_dataset.targets
    X_val = val_dataset.tab_data
    y_val = val_dataset.targets
    X_test = test_dataset.tab_data
    y_test = test_dataset.targets
    
    lgb_model = get_lightgbm_baseline()
    lgb_model.fit(X_train, y_train)
    
    print("Calibrating LightGBM with Validation data...")
    val_preds_lgb = lgb_model.predict_proba(X_val)
    lgb_calibrators = []
    for i in range(5):
        ir = IsotonicRegression(out_of_bounds='clip')
        ir.fit(val_preds_lgb[:, i], y_val[:, i])
        lgb_calibrators.append(ir)
        
    def predict_lgb_calibrated(X):
        raw_preds = lgb_model.predict_proba(X)
        cal_preds = np.zeros_like(raw_preds)
        for i in range(5):
            cal_preds[:, i] = lgb_calibrators[i].predict(raw_preds[:, i])
        return np.maximum.accumulate(cal_preds, axis=1)
        
    lgb_preds = predict_lgb_calibrated(X_test)
    evaluate_predictions(y_test, lgb_preds, test_df, "LightGBM")
    
    def get_lgb_preds(tab, seq):
        return predict_lgb_calibrated(tab)
        
    evaluate_policy_regret(test_df, tabular_features, X_test, test_dataset.seq_data, get_lgb_preds, "LightGBM")
    
    print("\n--- Training Hybrid NN ---")
    hybrid = HybridModel(tab_features=len(tabular_features), seq_features=4)
    train_nn(hybrid, train_loader, val_loader, epochs=3, seed=42)
    
    print("Calibrating NN with Validation data...")
    calibrators = calibrate_nn(hybrid, val_loader)
    
    nn_preds = predict_nn(hybrid, X_test, test_dataset.seq_data, calibrators)
    evaluate_predictions(y_test, nn_preds, test_df, "Hybrid (GRU + Tabular)")
    
    def get_nn_preds(tab, seq):
        return predict_nn(hybrid, tab, seq, calibrators)
        
    evaluate_policy_regret(test_df, tabular_features, X_test, test_dataset.seq_data, get_nn_preds, "Hybrid (GRU + Tabular)")

if __name__ == "__main__":
    main()
