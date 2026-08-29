import os
import pytest
from pydantic_core import ValidationError

def test_production_config_isolation_jwt():
    # Ensure environment is clean
    if "JWT_SECRET_KEY" in os.environ:
        del os.environ["JWT_SECRET_KEY"]
    
    # Attempting to load SecurityConfig directly without env variables should fail
    # We must mock .env file loading if the local .env actually exists, 
    # but the simplest proof is attempting instantiation explicitly.
    from app.core.config import SecurityConfig
    
    # Without environment variables or a matching .env loaded into os.environ,
    # the Pydantic Field(..., description="...") will throw ValidationError.
    # To truly isolate this test, we temporarily remove .env if it exists
    env_path = ".env"
    env_exists = os.path.exists(env_path)
    if env_exists:
        os.rename(env_path, ".env.testbak")
        
    try:
        with pytest.raises(ValidationError) as exc_info:
            SecurityConfig()
            
        assert "JWT_SECRET_KEY" in str(exc_info.value)
    finally:
        if env_exists:
            os.rename(".env.testbak", env_path)

def test_production_config_isolation_razorpay():
    old_id = os.environ.get("RAZORPAY_KEY_ID")
    old_secret = os.environ.get("RAZORPAY_KEY_SECRET")
    old_webhook = os.environ.get("RAZORPAY_WEBHOOK_SECRET")
    
    if "RAZORPAY_KEY_ID" in os.environ:
        del os.environ["RAZORPAY_KEY_ID"]
    if "RAZORPAY_KEY_SECRET" in os.environ:
        del os.environ["RAZORPAY_KEY_SECRET"]
    if "RAZORPAY_WEBHOOK_SECRET" in os.environ:
        del os.environ["RAZORPAY_WEBHOOK_SECRET"]
        
    from app.core.config import RazorpayConfig
    
    env_path = ".env"
    env_exists = os.path.exists(env_path)
    if env_exists:
        os.rename(env_path, ".env.testbak")
        
    try:
        with pytest.raises(ValidationError) as exc_info:
            RazorpayConfig()
            
        assert "KEY_ID" in str(exc_info.value)
        assert "KEY_SECRET" in str(exc_info.value)
        assert "WEBHOOK_SECRET" in str(exc_info.value)
    finally:
        if env_exists:
            os.rename(".env.testbak", env_path)
        if old_id is not None:
            os.environ["RAZORPAY_KEY_ID"] = old_id
        if old_secret is not None:
            os.environ["RAZORPAY_KEY_SECRET"] = old_secret
        if old_webhook is not None:
            os.environ["RAZORPAY_WEBHOOK_SECRET"] = old_webhook
