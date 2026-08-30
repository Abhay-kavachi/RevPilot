import os
import sys
import numpy as np
import joblib
from sklearn.isotonic import IsotonicRegression

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from ml.dataset import prepare_data, RevPilotDataset
from ml.models import get_lightgbm_baseline

def calibrate_sklearn(model, X_val, y_val):
    raw_preds = model.predict_proba(X_val)
    calibrators = []
    for i in range(5):
        ir = IsotonicRegression(out_of_bounds='clip')
        ir.fit(raw_preds[:, i], y_val[:, i])
        calibrators.append(ir)
    return calibrators

def main():
    data_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'world_model_events_seed42.parquet')
    print(f"Loading data from {data_path}...")
    train_df, val_df, test_df, tabular_features = prepare_data(data_path)
    
    train_ds = RevPilotDataset(train_df, tabular_features)
    val_ds = RevPilotDataset(val_df, tabular_features)
    
    print("Training LightGBM Production Model...")
    model = get_lightgbm_baseline()
    model.models = [model.models[i].__class__(n_estimators=100, learning_rate=0.05, n_jobs=-1, random_state=42) for i in range(5)]
    model.fit(train_ds.tab_data, train_ds.targets)
    
    print("Calibrating Production Model on Validation Set...")
    calibrators = calibrate_sklearn(model, val_ds.tab_data, val_ds.targets)
    
    out_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'prod_model')
    os.makedirs(out_dir, exist_ok=True)
    
    model_path = os.path.join(out_dir, 'lgbm_model.pkl')
    cals_path = os.path.join(out_dir, 'lgbm_calibrators.pkl')
    features_path = os.path.join(out_dir, 'tabular_features.pkl')
    
    joblib.dump(model, model_path)
    joblib.dump(calibrators, cals_path)
    joblib.dump(tabular_features, features_path)
    
    print(f"Successfully exported production model to {out_dir}")

if __name__ == "__main__":
    main()
