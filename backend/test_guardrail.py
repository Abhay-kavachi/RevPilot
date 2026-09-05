import pytest
from app.economics.engine import ActionEvaluation, EconomicEngine
from app.core.policy import PolicyManager, EconomicPolicy, ProbabilityGuardrailConfig
from unittest.mock import patch, MagicMock

# Create a mock policy config to use for testing
def create_mock_policy(enabled=True, abs_tol=10, rel_tol=0.01, p_thresh=0.10):
    policy = MagicMock(spec=EconomicPolicy)
    policy.probability_preserving_guardrail = ProbabilityGuardrailConfig(
        enabled=enabled,
        minimum_absolute_tolerance_paise=abs_tol,
        relative_tolerance=rel_tol,
        probability_threshold=p_thresh
    )
    return policy

def create_eval(action, enr, p):
    return ActionEvaluation(
        action_type=action,
        expected_value=enr, # Just use enr as expected_value for ease of mocking
        success_probability=p,
        cost=0,
        friction=0,
        risk=0,
        final_enr=enr,
        probability_source="MOCK"
    )

def test_guardrail_triggers():
    engine = EconomicEngine()
    engine.policy = create_mock_policy(abs_tol=10, rel_tol=0.01, p_thresh=0.10)
    
    # ENR winner is A, but B is within 10 paise and has >10pp probability advantage
    evals = [
        create_eval("A", 1320, 0.55),
        create_eval("B", 1310, 0.71)
    ]
    
    result = engine._apply_probability_guardrail(evals)
    
    assert result[0].action_type == "B"
    assert result[0].guardrail_applied is True
    assert "Probability Guardrail" in result[0].guardrail_reason

def test_economic_dominance_wins():
    engine = EconomicEngine()
    engine.policy = create_mock_policy(abs_tol=10, rel_tol=0.01, p_thresh=0.10)
    
    # ENR winner is A. B has high probability but ENR gap is 220 paise (exceeds tolerance of max(10, 13.2) = 13.2)
    evals = [
        create_eval("A", 1320, 0.55),
        create_eval("B", 1100, 0.71)
    ]
    
    result = engine._apply_probability_guardrail(evals)
    
    assert result[0].action_type == "A"
    assert result[0].guardrail_applied is False

def test_probability_difference_too_small():
    engine = EconomicEngine()
    engine.policy = create_mock_policy(abs_tol=10, rel_tol=0.01, p_thresh=0.10)
    
    # ENR winner A. B is within ENR tolerance but probability gap is only 2pp (< 10pp)
    evals = [
        create_eval("A", 1320, 0.55),
        create_eval("B", 1310, 0.57)
    ]
    
    result = engine._apply_probability_guardrail(evals)
    
    assert result[0].action_type == "A"
    assert result[0].guardrail_applied is False

def test_equal_enr_higher_probability_wins():
    engine = EconomicEngine()
    engine.policy = create_mock_policy(abs_tol=10, rel_tol=0.01, p_thresh=0.10)
    
    # A and B have equal ENR. B has higher probability.
    evals = [
        create_eval("A", 1320, 0.55),
        create_eval("B", 1320, 0.71)
    ]
    
    result = engine._apply_probability_guardrail(evals)
    
    assert result[0].action_type == "B"
    assert result[0].guardrail_applied is True

def test_negative_enr_unchanged():
    engine = EconomicEngine()
    engine.policy = create_mock_policy()
    
    # All actions have negative ENR
    evals = [
        create_eval("A", -50, 0.55),
        create_eval("B", -10, 0.71)
    ]
    
    # Should be pre-sorted by engine
    evals_sorted = sorted(evals, key=lambda x: x.final_enr, reverse=True)
    
    result = engine._apply_probability_guardrail(evals_sorted)
    
    # Original ENR winner (-10) should stay at top
    assert result[0].action_type == "B"
    assert result[0].guardrail_applied is False

def test_multiple_candidates_compare_to_enr_winner():
    engine = EconomicEngine()
    engine.policy = create_mock_policy(abs_tol=10, rel_tol=0.01, p_thresh=0.10)
    
    # A is winner.
    # B is within 10 paise, P = 0.60
    # C is within 20 paise (OUTSIDE tolerance), P = 0.71
    evals = [
        create_eval("A", 1320, 0.55),
        create_eval("B", 1315, 0.60),
        create_eval("C", 1300, 0.71)
    ]
    
    result = engine._apply_probability_guardrail(evals)
    
    # Neither B (prob gap < 10pp) nor C (enr gap > tolerance) should win.
    assert result[0].action_type == "A"
    
    # Now let's make B have a high enough prob gap
    evals2 = [
        create_eval("A", 1320, 0.55),
        create_eval("B", 1315, 0.66), # 11pp gap
        create_eval("C", 1300, 0.71)  # Too far in ENR
    ]
    result2 = engine._apply_probability_guardrail(evals2)
    assert result2[0].action_type == "B"
    
def test_scale_awareness():
    engine = EconomicEngine()
    engine.policy = create_mock_policy(abs_tol=10, rel_tol=0.01, p_thresh=0.10)
    
    # Large payment: ENR = 100,000 paise (1,000 INR)
    # 1% relative tolerance = 1,000 paise (10 INR)
    # So an ENR gap of 500 paise (5 INR) should be within tolerance
    evals_large = [
        create_eval("A", 100000, 0.50),
        create_eval("B", 99500,  0.65)
    ]
    res_large = engine._apply_probability_guardrail(evals_large)
    assert res_large[0].action_type == "B"
    
    # Small payment: ENR = 500 paise (5 INR)
    # 1% relative tolerance = 5 paise
    # Absolute tolerance floor = 10 paise
    # So an ENR gap of 15 paise should be OUTSIDE tolerance
    evals_small = [
        create_eval("A", 500, 0.50),
        create_eval("B", 485, 0.65)
    ]
    res_small = engine._apply_probability_guardrail(evals_small)
    assert res_small[0].action_type == "A"

def test_guardrail_disabled():
    engine = EconomicEngine()
    engine.policy = create_mock_policy(enabled=False, abs_tol=10000, rel_tol=1.0, p_thresh=0.0)
    
    # B dominates A in probability, and policy tolerances are huge, but guardrail is disabled
    evals = [
        create_eval("A", 1320, 0.55),
        create_eval("B", 1310, 0.99)
    ]
    
    result = engine._apply_probability_guardrail(evals)
    assert result[0].action_type == "A"
