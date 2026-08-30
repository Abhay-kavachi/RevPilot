import pytest
import numpy as np
import sys
from unittest.mock import patch
from app.economics.ml_predictor import ml_predictor, MLPredictor

def test_structural_no_razorpay_imports():
    """Assert MLPredictor file doesn't import Razorpay or executors."""
    with open("app/economics/ml_predictor.py", "r") as f:
        content = f.read()
    lines = content.split('\n')
    for line in lines:
        if line.strip().startswith('import') or line.strip().startswith('from'):
            assert "razorpay" not in line.lower(), "ML predictor must never import razorpay."
            assert "executor" not in line.lower(), "ML predictor must never import executor."

def test_feature_builder_parity():
    """
    Assert exact order parity between training features and production features.
    """
    import pandas as pd
    from ml.features import FeatureBuilder, FeatureSchema
    
    # Simulate a row of raw event data (mimicking the parquet row)
    raw_data = {
        "amount_at_risk_paise": [50000],
        "case_age_hours": [24.0],
        "recent_30d_failures": [2],
        "step": [1],
        "action": ["CREATE_PAYMENT_LINK"]
    }
    df = pd.DataFrame(raw_data)
    
    # === OFFLINE (TRAINING) PIPELINE ===
    df_train = pd.get_dummies(df, columns=["action"])
    for col in FeatureSchema.features:
        if col not in df_train.columns:
            df_train[col] = 0.0
    df_train["amount_at_risk_paise_log"] = np.log1p(df_train["amount_at_risk_paise"])
    
    # The offline vector that would go to training
    offline_vector = df_train.iloc[0][FeatureSchema.features].values.astype(np.float32)
    
    # === ONLINE (SERVING) PIPELINE ===
    builder = FeatureBuilder()
    raw = df.iloc[0]
    online_vector = builder.build_single(
        amount_at_risk_paise=raw["amount_at_risk_paise"],
        age_hours=raw["case_age_hours"],
        recent_30d_failures=raw["recent_30d_failures"],
        attempt_count=raw["step"],
        action=raw["action"]
    )
    
    # Assert exact numerical and dimensional equality
    assert np.array_equal(offline_vector, online_vector), "Offline and Online feature vectors do not match!"

def test_schema_validation_failure():
    """
    Assert that if metadata.json has a version mismatch, the Predictor refuses to load.
    """
    import json
    from unittest.mock import patch, mock_open
    
    bad_metadata = {
        "model_version": "1.0",
        "feature_schema_version": "99.9.9",  # INTENTIONAL MISMATCH
        "horizons": ["1h"],
        "features": []
    }
    
    with patch("app.core.config.settings.ML_ENABLED", True):
        with patch("builtins.open", mock_open(read_data=json.dumps(bad_metadata))):
            with pytest.raises(RuntimeError, match="MODEL_SCHEMA_MISMATCH"):
                _ = MLPredictor(model_dir="/fake")

@pytest.mark.skipif(ml_predictor is None or not ml_predictor.available, reason="ML Model not available")
def test_action_conditioning_changes_probability():
    """
    Ensure the probability changes purely based on the action selected,
    proving the model is action-conditioned and distinguishing between choices.
    """
    # Context is identical
    context = dict(
        amount_at_risk_paise=100000,
        age_hours=48.0,
        recent_30d_failures=1,
        attempt_count=1,
        horizon="72h"
    )
    
    pred_cpl = ml_predictor.predict_recovery(**context, action="CREATE_PAYMENT_LINK")
    pred_retry = ml_predictor.predict_recovery(**context, action="RETRY_PAYMENT")
    pred_reminder = ml_predictor.predict_recovery(**context, action="SEND_REMINDER")
    
    # Assert they are not the same identical float
    assert pred_cpl.probability != pred_retry.probability, "CREATE_PAYMENT_LINK vs RETRY identical!"
    assert pred_cpl.probability != pred_reminder.probability, "CREATE_PAYMENT_LINK vs REMINDER identical!"

def test_ml_fallback_observability():
    """
    Ensure that ML_ENABLED=True with a missing model raises FileNotFoundError
    (preventing silent fallback).
    """
    import os
    with patch("app.core.config.settings.ML_ENABLED", True):
        with pytest.raises(FileNotFoundError, match="MODEL_UNAVAILABLE"):
            _ = MLPredictor(model_dir="/invalid_fake_path_that_does_not_exist")

def test_horizon_contract():
    """
    Ensure an unknown horizon explicitly fails instead of guessing.
    """
    if ml_predictor is None or not ml_predictor.available:
        pytest.skip("ML Model not available")
        
    with pytest.raises(ValueError, match="Unknown horizon"):
        ml_predictor.predict_recovery(
            amount_at_risk_paise=100000,
            age_hours=48.0,
            recent_30d_failures=1,
            attempt_count=1,
            action="CREATE_PAYMENT_LINK",
            horizon="2000h" # Invalid
        )
