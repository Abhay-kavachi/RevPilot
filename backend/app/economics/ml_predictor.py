import os
import json
import numpy as np
import joblib
from pydantic import BaseModel
from app.core.config import settings

# Do not import razorpay or executors here. ML Predictor is purely computational.

class PredictionResult(BaseModel):
    probability: float
    source: str
    model_version: str
    feature_schema_version: str
    horizon: str

class MLPredictor:
    def __init__(self, model_dir: str = None):
        if not settings.ML_ENABLED:
            self.available = False
            return
            
        if not model_dir:
            model_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "prod_model")
            
        try:
            with open(os.path.join(model_dir, 'metadata.json'), 'r') as f:
                self.metadata = json.load(f)
                
            # Import feature builder dynamically to avoid cyclic dependency if needed, or directly
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
            from ml.features import FeatureBuilder
            
            self.builder = FeatureBuilder()
            self.builder.schema.validate_artifact_schema(self.metadata)
            
            self.model = joblib.load(os.path.join(model_dir, 'lgbm_model.pkl'))
            self.calibrators = joblib.load(os.path.join(model_dir, 'lgbm_calibrators.pkl'))
            self.available = True
        except FileNotFoundError as e:
            raise FileNotFoundError(f"MODEL_UNAVAILABLE: ML_ENABLED is true but artifact is missing. {e}")
        except Exception as e:
            raise RuntimeError(f"MODEL_UNAVAILABLE: Failed to load ML artifacts. {e}")

    def predict_calibrated_sklearn(self, X):
        raw = self.model.predict_proba(X)
        cal = np.zeros_like(raw)
        for i in range(len(self.metadata['horizons'])):
            cal[:, i] = self.calibrators[i].predict(raw[:, i])
        return np.maximum.accumulate(cal, axis=1)

    def predict_recovery(self, amount_at_risk_paise: int, age_hours: float, recent_30d_failures: int, attempt_count: int, action: str, horizon: str) -> PredictionResult:
        if not self.available:
            raise RuntimeError("predict_recovery called but ML is disabled.")
            
        if horizon not in self.metadata['horizons']:
            raise ValueError(f"Unknown horizon '{horizon}'. Must be one of {self.metadata['horizons']}")
            
        if action == "NO_ACTION" or action == "CLOSE_CASE":
            return PredictionResult(
                probability=0.0, 
                source="ML_DETERMINISTIC", 
                model_version="1.0", 
                feature_schema_version=self.metadata['version'], 
                horizon=horizon
            )

        # 1. Feature Representation Contract
        x = self.builder.build_single(amount_at_risk_paise, age_hours, recent_30d_failures, attempt_count, action)
            
        # 2. Prediction
        X_batch = np.array([x])
        calibrated_preds = self.predict_calibrated_sklearn(X_batch)
        
        # 3. Horizon Mapping
        h_idx = self.metadata['horizons'].index(horizon)
        probability = float(calibrated_preds[0, h_idx])
        
        return PredictionResult(
            probability=probability,
            source="ML",
            model_version="LightGBM_Prod_v1",
            feature_schema_version=self.metadata['version'],
            horizon=horizon
        )

# Initialize global instance
if settings.ML_ENABLED:
    ml_predictor = MLPredictor()
else:
    ml_predictor = None
