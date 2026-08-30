import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app.economics.engine import EconomicEngine

def print_evals(evaluations, title):
    print("=====================================================================================================================")
    print(title)
    print("=====================================================================================================================")
    print(f"{'Action':<25} | {'Probability':<12} | {'EV (Paise)':<12} | {'Cost':<6} | {'Friction':<8} | {'Risk':<6} | {'ENR (Paise)':<12} | {'Source'}")
    print("-" * 117)
    
    for ev in evaluations:
        prob_str = f"{ev.success_probability:.4f}"
        print(f"{ev.action_type:<25} | {prob_str:<12} | {ev.expected_value:<12} | {ev.cost:<6} | {ev.friction:<8} | {ev.risk:<6} | {ev.final_enr:<12} | {ev.probability_source}")
    print("=====================================================================================================================\n")

def main():
    engine = EconomicEngine()

    # CASE A: High Value
    print("Context: Amount = 50,000 INR | Loyal | Recent Failures = 0")
    evals_A = engine.evaluate_case(
        case_type="failed_payment",
        amount_at_risk=5000000,
        attempt_count=0,
        age_days=0,
        failure_reason="insufficient_funds",
        customer_history_score=1.0,
        recent_30d_failures=0
    )
    print_evals(evals_A, "CASE A: HIGH VALUE RECOVERY")
    
    # CASE B: Marginal Value
    print("Context: Amount = 28 INR | High Risk | Recent Failures = 1")
    evals_B = engine.evaluate_case(
        case_type="failed_payment",
        amount_at_risk=2800,
        attempt_count=1,
        age_days=0,
        failure_reason="insufficient_funds",
        customer_history_score=0.0,
        recent_30d_failures=1
    )
    print_evals(evals_B, "CASE B: MARGINAL VALUE (HIGHER PROBABILITY != HIGHER ECONOMIC VALUE)")

    # CASE C: Hard Stop
    print("Context: Amount = 5 INR | High Risk | Recent Failures = 3")
    evals_C = engine.evaluate_case(
        case_type="failed_payment",
        amount_at_risk=500,
        attempt_count=2,
        age_days=0,
        failure_reason="insufficient_funds",
        customer_history_score=0.0,
        recent_30d_failures=3
    )
    print_evals(evals_C, "CASE C: NEGATIVE EXPECTED NET RETURN (STOP)")

if __name__ == "__main__":
    main()
