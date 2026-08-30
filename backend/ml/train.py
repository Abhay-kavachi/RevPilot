import torch
import torch.nn as nn
from torch.utils.data import DataLoader
import numpy as np
import pandas as pd
from dataset import prepare_data, RevPilotDataset
from models import HybridModel, get_logistic_baseline, get_lightgbm_baseline
from evaluate import evaluate_predictions
import os

def train_nn(model, train_loader, val_loader, epochs=5):
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    criterion = nn.BCELoss()
    
    print("Training PyTorch NN...")
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
            
        # Validation
        model.eval()
        val_loss = 0
        with torch.no_grad():
            for tab_x, seq_x, targets in val_loader:
                preds = model(tab_x, seq_x)
                val_loss += criterion(preds, targets).item()
                
        print(f"Epoch {epoch+1} | Train Loss: {train_loss/len(train_loader):.4f} | Val Loss: {val_loss/len(val_loader):.4f}")

def main():
    train_df, val_df, test_df, tabular_features = prepare_data()
    
    train_dataset = RevPilotDataset(train_df, tabular_features)
    val_dataset = RevPilotDataset(val_df, tabular_features)
    test_dataset = RevPilotDataset(test_df, tabular_features)
    
    train_loader = DataLoader(train_dataset, batch_size=256, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=256)
    test_loader = DataLoader(test_dataset, batch_size=256)
    
    # 1. Train LightGBM Baseline
    print("\n--- Training LightGBM Baseline ---")
    X_train = train_dataset.tab_data
    y_train = train_dataset.targets
    
    X_test = test_dataset.tab_data
    y_test = test_dataset.targets
    
    lgb_model = get_lightgbm_baseline()
    lgb_model.fit(X_train, y_train)
    
    lgb_preds = lgb_model.predict_proba(X_test)
    
    # Evaluate LightGBM
    evaluate_predictions(y_test, lgb_preds, test_df, "LightGBM")
    
    # 2. Train Hybrid NN
    print("\n--- Training Hybrid NN ---")
    hybrid = HybridModel(tab_features=len(tabular_features), seq_features=3)
    train_nn(hybrid, train_loader, val_loader, epochs=3)
    
    hybrid.eval()
    nn_preds = []
    with torch.no_grad():
        for tab_x, seq_x, _ in test_loader:
            preds = hybrid(tab_x, seq_x)
            nn_preds.append(preds.numpy())
            
    nn_preds = np.concatenate(nn_preds, axis=0)
    evaluate_predictions(y_test, nn_preds, test_df, "Hybrid (GRU + Tabular)")

if __name__ == "__main__":
    main()
