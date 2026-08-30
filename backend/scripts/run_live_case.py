import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app.economics.engine import EconomicEngine

def print_evals(evaluations, title):
    print("==========================================================================================")
    print(title)
    print("==========================================================================================")
    print(f"{'Action':<25} | {'Probability':<12} | {'EV (Paise)':<12} | {'Cost':<6} | {'Friction':<8} | {'Risk':<6} | {'ENR (Paise)':<12} | {'Source'}")
    print("-" * 115)
    
    for ev in evaluations:
        prob_str = f"{ev.success_probability:.4f}"
        print(f"{ev.action_type:<25} | {prob_str:<12} | {ev.expected_value:<12} | {ev.cost:<6} | {ev.friction:<8} | {ev.risk:<6} | {ev.final_enr:<12} | {ev.probability_source}")
    print()

def main():
    amount = 500000
    age = 2
    recent_failures = 1
    attempts = 1
    
    print(f"Context: Amount = 5,000 INR, Age = {age} days, Failures = {recent_failures}, Attempts = {attempts}\n")
    
    # 1. Run WITH ML
    engine_ml = EconomicEngine()
    evals_ml = engine_ml.evaluate_case(
        case_type="failed_payment",
        amount_at_risk=amount,
        attempt_count=attempts,
        age_days=age,
        failure_reason="insufficient_funds",
        customer_history_score=1.0,
        recent_30d_failures=recent_failures
    )
    print_evals(evals_ml, "LIVE REVPILOT DECISION (ML ENABLED)")
    
    # 2. Run WITHOUT ML (Policy Fallback)
    with patch("app.economics.ml_predictor.ml_predictor.available", False):
        engine_fallback = EconomicEngine()
        evals_fallback = engine_fallback.evaluate_case(
            case_type="failed_payment",
            amount_at_risk=amount,
            attempt_count=attempts,
            age_days=age,
            failure_reason="insufficient_funds",
            customer_history_score=1.0,
            recent_30d_failures=recent_failures
        )
        print_evals(evals_fallback, "LIVE REVPILOT DECISION (ML DISABLED / POLICY FALLBACK)")

if __name__ == "__main__":
    main()
