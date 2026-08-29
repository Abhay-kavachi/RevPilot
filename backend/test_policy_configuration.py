import pytest
import os
import json
from unittest.mock import patch
from app.core.policy import PolicyManager
from app.agent.schemas import AgentContext
from app.economics.engine import EconomicEngine

@pytest.fixture
def mock_policy_file(tmp_path):
    policy_data = {
      "economic_policy": {
        "version": "test-1.0",
        "base_probabilities": {
          "CREATE_PAYMENT_LINK": 0.90,  # Highly inflated
          "SEND_REMINDER": 0.10,
          "NO_ACTION": 0.0
        },
        "failure_reason_multipliers": {
          "test_reason": 0.5,
          "unknown": 0.6
        },
        "attempt_adjustments": [
          { "attempt_count": 0, "multiplier": 1.0 },
          { "attempt_count": 2, "multiplier": 0.1 }
        ],
        "age_adjustments": [
          { "max_days": 999, "multiplier": 1.0 }
        ],
        "action_costs_paise": {
          "CREATE_PAYMENT_LINK": 100,
          "SEND_REMINDER": 5,
          "NO_ACTION": 0
        },
        "action_frictions_paise": {
          "CREATE_PAYMENT_LINK": 0,
          "SEND_REMINDER": 0,
          "NO_ACTION": 0
        },
        "action_risks_paise": {
          "CREATE_PAYMENT_LINK": 0,
          "SEND_REMINDER": 0,
          "NO_ACTION": 0
        }
      },
      "recovery_policy": {
        "version": "test-1.0",
        "max_attempts": 2,
        "min_expected_value": 0.0,
        "allowed_actions": ["CREATE_PAYMENT_LINK", "SEND_REMINDER", "NO_ACTION"],
        "stop_threshold": 0.0
      }
    }
    
    file_path = tmp_path / "test_policy.json"
    with open(file_path, "w") as f:
        json.dump(policy_data, f)
    return str(file_path)

def test_policy_drives_economic_engine(mock_policy_file):
    # Load custom policy
    manager = PolicyManager(policy_path=mock_policy_file)
    
    # Override the global manager inside engine
    with patch("app.economics.engine.policy_manager", manager):
        engine = EconomicEngine()
        
        # Test 1: Base probabilities apply (with 'unknown' failure reason multiplier of 0.6)
        # 0.90 * 0.6 = 0.54
        evals = engine.evaluate_case("F", 1000, attempt_count=0)
        link_eval = next(e for e in evals if e.action_type == "CREATE_PAYMENT_LINK")
        assert link_eval.success_probability == pytest.approx(0.54)
        assert link_eval.expected_value == 540 # 1000 * 0.54
        assert link_eval.final_enr == 440 # 540 - 100 cost
        
        # Test 2: Attempt adjustment applies (multiplier 0.1)
        # 0.54 * 0.1 = 0.054
        evals_attempt = engine.evaluate_case("F", 1000, attempt_count=2)
        link_eval_attempt = next(e for e in evals_attempt if e.action_type == "CREATE_PAYMENT_LINK")
        assert link_eval_attempt.success_probability == pytest.approx(0.054)
        
        # Test 3: Failure reason multiplier applies ('test_reason' multiplier 0.5)
        # 0.90 * 0.5 = 0.45
        evals_reason = engine.evaluate_case("F", 1000, attempt_count=0, failure_reason="test_reason")
        link_eval_reason = next(e for e in evals_reason if e.action_type == "CREATE_PAYMENT_LINK")
        assert link_eval_reason.success_probability == pytest.approx(0.45)
        
def test_money_units_are_integers():
    # Prove that the configuration prevents float injection
    from app.core.policy import EconomicPolicy
    from pydantic_core import ValidationError
    
    # Passing a float like 2.50 should be explicitly rejected by StrictInt
    with pytest.raises(ValidationError) as exc_info:
        EconomicPolicy(
            version="1.0",
            base_probabilities={},
            failure_reason_multipliers={},
            attempt_adjustments=[],
            age_adjustments=[],
            action_costs_paise={"TEST": 2.50},  # Float rejected
            action_frictions_paise={"TEST": 500},
            action_risks_paise={"TEST": 0}
        )
        
    assert "Input should be a valid integer" in str(exc_info.value)

def test_probability_input_validation():
    engine = EconomicEngine()
    
    with pytest.raises(ValueError, match="customer_history_score must be between 0 and 1"):
        engine.evaluate_case("F", 1000, 0, customer_history_score=-0.5)
        
    with pytest.raises(ValueError, match="customer_history_score must be between 0 and 1"):
        engine.evaluate_case("F", 1000, 0, customer_history_score=1.5)
        
    # Valid input shouldn't raise exception
    engine.evaluate_case("F", 1000, 0, customer_history_score=0.95)
