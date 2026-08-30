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
    from ml.features import FeatureBuilder, FeatureSchema
    
    # Generate vector using builder
    builder = FeatureBuilder()
    vec = builder.build_single(
        amount_at_risk_paise=50000,
        age_hours=24.0,
        recent_30d_failures=2,
        attempt_count=1,
        action="CREATE_PAYMENT_LINK"
    )
    
    # Assert manual offsets based on expected schema
    # "amount_at_risk_paise_log"
    assert vec[FeatureSchema.features.index("amount_at_risk_paise_log")] == np.float32(np.log1p(50000))
    assert vec[FeatureSchema.features.index("case_age_hours")] == 24.0
    assert vec[FeatureSchema.features.index("recent_30d_failures")] == 2
    assert vec[FeatureSchema.features.index("step")] == 1
    assert vec[FeatureSchema.features.index("action_CREATE_PAYMENT_LINK")] == 1.0
    assert vec[FeatureSchema.features.index("action_RETRY_PAYMENT")] == 0.0

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
