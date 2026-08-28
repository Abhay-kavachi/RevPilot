import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.economics.engine import EconomicEngine

def test_engine():
    engine = EconomicEngine()
    
    print("\n--- Positive EV Case ---")
    # High amount at risk (₹5000 = 500000 paise)
    evals = engine.evaluate_case("FAILED_PAYMENT", 500000, attempt_count=0)
    for e in evals:
        print(f"{e.action_type:30} | ENR: {e.final_enr:8} | EV: {e.expected_value:8} | P: {e.success_probability:.2f} | C+F+D: {e.cost + e.friction + e.risk}")
    
    print("\n--- Negative EV Case ---")
    # Tiny amount at risk (₹5 = 500 paise)
    evals = engine.evaluate_case("FAILED_PAYMENT", 500, attempt_count=0)
    for e in evals:
        print(f"{e.action_type:30} | ENR: {e.final_enr:8} | EV: {e.expected_value:8} | P: {e.success_probability:.2f} | C+F+D: {e.cost + e.friction + e.risk}")

    print("\n--- Borderline Case (Diminished Returns) ---")
    # High attempt count reduces probability
    evals = engine.evaluate_case("FAILED_PAYMENT", 2000, attempt_count=5)
    for e in evals:
        print(f"{e.action_type:30} | ENR: {e.final_enr:8} | EV: {e.expected_value:8} | P: {e.success_probability:.2f} | C+F+D: {e.cost + e.friction + e.risk}")

if __name__ == "__main__":
    test_engine()
