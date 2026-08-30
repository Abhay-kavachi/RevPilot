import numpy as np
from typing import List

class FeatureSchema:
    version = "1.0.0"
    horizons = ["1h", "6h", "24h", "72h", "168h"]
    features = [
        "amount_at_risk_paise_log",
        "case_age_hours",
        "recent_30d_failures",
        "step",
        "action_CREATE_PAYMENT_LINK",
        "action_ESCALATE_TO_SUPPORT",
        "action_NO_ACTION",
        "action_RETRY_PAYMENT",
        "action_SEND_REMINDER"
    ]
    expected_count = len(features)
    
    @classmethod
    def validate_artifact_schema(cls, artifact_schema_dict: dict):
        if artifact_schema_dict.get("version") != cls.version:
            raise ValueError(f"MODEL_SCHEMA_MISMATCH: Artifact version {artifact_schema_dict.get('version')} != Runtime {cls.version}")
        if artifact_schema_dict.get("features") != cls.features:
            raise ValueError("MODEL_SCHEMA_MISMATCH: Feature ordering/naming mismatch.")
        if artifact_schema_dict.get("horizons") != cls.horizons:
            raise ValueError("MODEL_SCHEMA_MISMATCH: Horizon mismatch.")

class FeatureBuilder:
    def __init__(self):
        self.schema = FeatureSchema()
        
    def build_single(self, amount_at_risk_paise: int, age_hours: float, recent_30d_failures: int, attempt_count: int, action: str) -> np.ndarray:
        x = np.zeros(self.schema.expected_count, dtype=np.float32)
        
        try:
            x[self.schema.features.index('amount_at_risk_paise_log')] = np.log1p(amount_at_risk_paise)
            x[self.schema.features.index('case_age_hours')] = age_hours
            x[self.schema.features.index('recent_30d_failures')] = recent_30d_failures
            x[self.schema.features.index('step')] = attempt_count
            
            action_col = f"action_{action}"
            if action_col in self.schema.features:
                x[self.schema.features.index(action_col)] = 1.0
        except ValueError as e:
            raise ValueError(f"Feature error: {e}")
            
        return x
