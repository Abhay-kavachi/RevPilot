import pytest
import os
from app.database.core import SessionLocal
from app.models.domain import RevenueRiskCase, CaseStatus, CaseAction
from app.economics.engine import EconomicEngine
from app.agent.agent import RevPilotAgent
from app.agent.action_selector import ActionSelector
from app.agent.planner import AgentPlanner
from app.agent.schemas import AgentContext

@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()

def test_cheap_action_beats_expensive():
    """
    Even if an action has higher probability, a massive cost should disqualify it
    relative to a slightly lower probability but zero cost action.
    """
    engine = EconomicEngine()
    # Mutate policy config directly instead of old ACTION_PARAMS
    from app.core.policy import policy_manager
    policy = policy_manager.economic_policy
    
    # Store old values
    old_p_retry = policy.base_probabilities.get("RETRY_PAYMENT", 0.0)
    old_c_retry = policy.action_costs.get("RETRY_PAYMENT", 0.0)
    old_p_link = policy.base_probabilities.get("CREATE_PAYMENT_LINK", 0.0)
    old_c_link = policy.action_costs.get("CREATE_PAYMENT_LINK", 0.0)
    
    # Apply adversarial conditions
    policy.base_probabilities["RETRY_PAYMENT"] = 0.90
    policy.action_costs["RETRY_PAYMENT"] = 10000
    
    policy.base_probabilities["CREATE_PAYMENT_LINK"] = 0.80
    policy.action_costs["CREATE_PAYMENT_LINK"] = 10
    
    evals = engine.evaluate_case("FAILED_PAYMENT", 1000, 0)
    
    # Restore
    policy.base_probabilities["RETRY_PAYMENT"] = old_p_retry
    policy.action_costs["RETRY_PAYMENT"] = old_c_retry
    policy.base_probabilities["CREATE_PAYMENT_LINK"] = old_p_link
    policy.action_costs["CREATE_PAYMENT_LINK"] = old_c_link
    
    assert evals[0].action_type == "CREATE_PAYMENT_LINK"

def test_high_probability_outweighed_by_friction():
    engine = EconomicEngine()
    from app.core.policy import policy_manager
    policy = policy_manager.economic_policy
    
    old_f_link = policy.action_frictions.get("CREATE_PAYMENT_LINK", 0.0)
    policy.action_frictions["CREATE_PAYMENT_LINK"] = 50000 # Massive friction
    
    evals = engine.evaluate_case("FAILED_PAYMENT", 1000, 0)
    
    policy.action_frictions["CREATE_PAYMENT_LINK"] = old_f_link
    
    assert evals[0].action_type != "CREATE_PAYMENT_LINK"

def test_repeated_retries_become_negative_ev_and_stop():
    engine = EconomicEngine()
    selector = ActionSelector()
    
    context = AgentContext(
        case_id="1", case_type="FAILED_PAYMENT", status="OPEN", amount_at_risk=500, 
        attempt_count=5, max_attempts=3, recovery_deadline=None, action_history=[],
        is_recoverable=True, days_since_creation=0, failure_reason="unknown"
    )
    
    evals_attempt_5 = engine.evaluate_case("FAILED_PAYMENT", 500, 5)
    action = selector.select_action(context, evals_attempt_5)
    
    assert action in ["CLOSE_CASE", "NO_ACTION"]
