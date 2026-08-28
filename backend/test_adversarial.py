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

def test_cheap_action_beats_expensive(db):
    engine = EconomicEngine()
    # Modify params temporarily for the test to prove logic
    original_params = engine.ACTION_PARAMS["FAILED_PAYMENT"].copy()
    
    # Expensive action: EV is high, but cost is massive
    engine.ACTION_PARAMS["FAILED_PAYMENT"]["RETRY_PAYMENT_OPPORTUNITY"] = {"P": 0.90, "C": 10000, "F": 0, "D": 0}
    # Cheap action: EV is lower, but cost is tiny
    engine.ACTION_PARAMS["FAILED_PAYMENT"]["CREATE_PAYMENT_LINK"] = {"P": 0.50, "C": 10, "F": 0, "D": 0}
    
    evals = engine.evaluate_case("FAILED_PAYMENT", 5000, 0)
    # Retry EV: 5000 * 0.9 = 4500. Cost = 10000. ENR = -5500
    # Link EV: 5000 * 0.5 = 2500. Cost = 10. ENR = 2490
    
    assert evals[0].action_type == "CREATE_PAYMENT_LINK"
    assert evals[0].final_enr > 0
    
    # Restore
    engine.ACTION_PARAMS["FAILED_PAYMENT"] = original_params

def test_high_probability_outweighed_by_friction(db):
    engine = EconomicEngine()
    original_params = engine.ACTION_PARAMS["FAILED_PAYMENT"].copy()
    
    engine.ACTION_PARAMS["FAILED_PAYMENT"]["RETRY_PAYMENT_OPPORTUNITY"] = {"P": 0.99, "C": 10, "F": 20000, "D": 0}
    evals = engine.evaluate_case("FAILED_PAYMENT", 5000, 0)
    
    # EV for Retry: 4950. ENR: 4950 - 10 - 20000 = -15060
    # Because Retry is so negative, the agent should reject it and pick the next best (CREATE_PAYMENT_LINK)
    assert evals[0].action_type == "CREATE_PAYMENT_LINK"
    
    engine.ACTION_PARAMS["FAILED_PAYMENT"] = original_params

def test_repeated_retries_become_negative_ev_and_stop(db):
    engine = EconomicEngine()
    selector = ActionSelector()
    
    # Use amount 500 so that SEND_REMINDER also becomes negative after decay
    context = AgentContext(
        case_id="mock", case_type="FAILED_PAYMENT", status=CaseStatus.OPEN,
        amount_at_risk=500, attempt_count=0, max_attempts=10
    )
    
    # Attempt 0: Positive
    evals = engine.evaluate_case("FAILED_PAYMENT", 500, 0)
    assert selector.select_action(context, evals) != "CLOSE_CASE"
    
    context.attempt_count = 5
    evals_attempt_5 = engine.evaluate_case("FAILED_PAYMENT", 500, 5)
    
    action = selector.select_action(context, evals_attempt_5)
    assert action == "CLOSE_CASE"
