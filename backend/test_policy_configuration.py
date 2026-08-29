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
          "test_reason": 0.5
        },
        "attempt_adjustments": [
          { "attempt_count": 0, "multiplier": 1.0 },
          { "attempt_count": 2, "multiplier": 0.1 }
        ],
        "age_adjustments": [
          { "max_days": 999, "multiplier": 1.0 }
        ],
        "action_costs": {
          "CREATE_PAYMENT_LINK": 100,
          "SEND_REMINDER": 5,
          "NO_ACTION": 0
        },
        "action_frictions": {
          "CREATE_PAYMENT_LINK": 0,
          "SEND_REMINDER": 0,
          "NO_ACTION": 0
        },
        "action_risks": {
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
        
        # Test 1: Base probabilities apply
        context = AgentContext(
            case_id="1", case_type="F", status="OPEN", amount_at_risk=1000, 
            attempt_count=0, max_attempts=3, recovery_deadline=None, action_history=[],
            is_recoverable=True, days_since_creation=0, failure_reason="unknown"
        )
        
        evals = engine.evaluate_case("F", 1000, attempt_count=0)
        link_eval = next(e for e in evals if e.action_type == "CREATE_PAYMENT_LINK")
        assert link_eval.success_probability == 0.90 # Configured in mock policy
        assert link_eval.expected_value == 900 # 1000 * 0.90
        assert link_eval.final_enr == 800 # 900 - 100 cost
        
        # Test 2: Attempt adjustment applies
        evals_attempt = engine.evaluate_case("F", 1000, attempt_count=2)
        link_eval_attempt = next(e for e in evals_attempt if e.action_type == "CREATE_PAYMENT_LINK")
        assert link_eval_attempt.success_probability == pytest.approx(0.09) # 0.90 base * 0.1 multiplier
        
        # Test 3: Failure reason multiplier applies
        evals_reason = engine.evaluate_case("F", 1000, attempt_count=0, failure_reason="test_reason")
        link_eval_reason = next(e for e in evals_reason if e.action_type == "CREATE_PAYMENT_LINK")
        assert link_eval_reason.success_probability == pytest.approx(0.45) # 0.90 * 0.5
