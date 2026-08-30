import os
import numpy as np
import joblib

class MLPredictor:
    def __init__(self, model_dir: str = None):
        if not model_dir:
            model_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "prod_model")
        
        self.model = joblib.load(os.path.join(model_dir, 'lgbm_model.pkl'))
        self.calibrators = joblib.load(os.path.join(model_dir, 'lgbm_calibrators.pkl'))
        self.tabular_features = joblib.load(os.path.join(model_dir, 'tabular_features.pkl'))
        
        # Determine the action index mappings for one-hot encoding
        self.action_features = [f for f in self.tabular_features if f.startswith("action_")]

    def predict_calibrated_sklearn(self, X):
        raw = self.model.predict_proba(X)
        cal = np.zeros_like(raw)
        for i in range(5):
            cal[:, i] = self.calibrators[i].predict(raw[:, i])
        return np.maximum.accumulate(cal, axis=1)

    def predict_recovery(self, amount_at_risk_paise: int, age_hours: float, recent_30d_failures: int, attempt_count: int, action: str, horizon: str = "72h") -> float:
        """
        Predicts the probability of recovery for a specific candidate action.
        """
        if action == "NO_ACTION" or action == "CLOSE_CASE":
            return 0.0

        # Construct feature vector
        x = np.zeros(len(self.tabular_features))
        
        # Core tabular features based on training representation
        x[self.tabular_features.index('amount_at_risk_paise_log')] = np.log1p(amount_at_risk_paise)
        x[self.tabular_features.index('case_age_hours')] = age_hours
        x[self.tabular_features.index('recent_30d_failures')] = recent_30d_failures
        x[self.tabular_features.index('step')] = attempt_count
        
        # One-hot encode the action
        action_col = f"action_{action}"
        if action_col in self.tabular_features:
            x[self.tabular_features.index(action_col)] = 1.0
            
        # Predict
        X_batch = np.array([x])
        calibrated_preds = self.predict_calibrated_sklearn(X_batch)
        
        # Map horizon
        horizon_map = {"1h": 0, "6h": 1, "24h": 2, "72h": 3, "168h": 4}
        h_idx = horizon_map.get(horizon, 3) # default 72h
        
        return float(calibrated_preds[0, h_idx])

# Singleton instance
try:
    ml_predictor = MLPredictor()
except FileNotFoundError:
    # Handle development environments where model isn't trained yet
    ml_predictor = None
