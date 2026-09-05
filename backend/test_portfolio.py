import pytest
from app.economics.portfolio import RecoveryPortfolioOptimizer
from app.economics.engine import ActionEvaluation

def test_shadow_price_computation():
    optimizer = RecoveryPortfolioOptimizer()
    
    # Mocking some evaluated actions
    # Case 1: High value, needs 250 paise
    case_1_evals = [
        ActionEvaluation(
            action_type="CREATE_PAYMENT_LINK",
            success_probability=0.7,
            expected_value=1000,
            cost=250,
            friction=50,
            risk=0,
            final_enr=700,
            probability_source="ML"
        )
    ]
    
    # Case 2: Low value, needs 50 paise
    case_2_evals = [
        ActionEvaluation(
            action_type="SEND_REMINDER",
            success_probability=0.5,
            expected_value=500,
            cost=50,
            friction=50,
            risk=0,
            final_enr=400,
            probability_source="ML"
        )
    ]
    
    cases_dict = {
        "c1": case_1_evals,
        "c2": case_2_evals
    }
    
    # At budget 50, it can only afford c2. ENR = 400.
    # At budget 250, it can afford c1. ENR = 700.
    # If budget=50 and increment=200, relaxed budget=250.
    # additional_enr = 700 - 400 = 300. mbv = 300 / 200 = 1.5
    
    shadow = optimizer.evaluate_shadow_price(cases_dict, budget_paise=50, increment_paise=200)
    
    assert shadow.base_budget == 50
    assert shadow.base_enr == 400
    assert shadow.increment == 200
    assert shadow.relaxed_budget == 250
    assert shadow.relaxed_enr == 700
    assert shadow.additional_enr == 300
    assert shadow.marginal_budget_value == 1.5

def test_shadow_price_no_change():
    optimizer = RecoveryPortfolioOptimizer()
    
    case_1_evals = [
        ActionEvaluation(
            action_type="SEND_REMINDER",
            success_probability=0.5,
            expected_value=500,
            cost=50,
            friction=50,
            risk=0,
            final_enr=400,
            probability_source="ML"
        )
    ]
    
    cases_dict = {"c1": case_1_evals}
    
    # At budget 50, it affords c1. ENR = 400.
    # At budget 250, it still only affords c1 (no other cases). ENR = 400.
    
    shadow = optimizer.evaluate_shadow_price(cases_dict, budget_paise=50, increment_paise=200)
    
    assert shadow.base_enr == 400
    assert shadow.relaxed_enr == 400
    assert shadow.additional_enr == 0
    assert shadow.marginal_budget_value == 0.0

def test_shadow_price_safety():
    # If the increment is 0 or negative, handle gracefully (in this case, MBV = 0.0)
    optimizer = RecoveryPortfolioOptimizer()
    cases_dict = {"c1": []}
    
    shadow = optimizer.evaluate_shadow_price(cases_dict, budget_paise=50, increment_paise=0)
    assert shadow.marginal_budget_value == 0.0
