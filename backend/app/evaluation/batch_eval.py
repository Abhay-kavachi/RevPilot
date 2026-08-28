import random
from typing import List, Dict
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from app.economics.engine import EconomicEngine

class SyntheticCase:
    def __init__(self, case_id: str, amount_paise: int):
        self.case_id = case_id
        self.amount_paise = amount_paise
        # Determines if this case will theoretically succeed on attempt N if tried
        # Fixed random seed means these values are reproducible
        self.success_rolls = [random.random() for _ in range(5)]
        
class Evaluator:
    def __init__(self):
        self.engine = EconomicEngine()
        self.max_attempts = 3
        
        # We use the same parameters as the engine to evaluate costs
        self.retry_params = self.engine.ACTION_PARAMS["FAILED_PAYMENT"]["RETRY_PAYMENT_OPPORTUNITY"]
        self.base_p = self.retry_params["P"]
        self.c = self.retry_params["C"]
        self.f = self.retry_params["F"]
        self.d = self.retry_params["D"]
        self.cost_per_attempt = self.c + self.f + self.d

    def generate_cases(self, count: int, seed: int = 42) -> List[SyntheticCase]:
        random.seed(seed)
        cases = []
        for i in range(count):
            if i < count // 3:
                # Micro-transactions (under ₹15) where costs eat margins
                amount = random.randint(1, 15) * 100
            else:
                # Normal distribution
                amount = int(random.expovariate(1.0 / 2000)) * 100
                if amount < 500: amount = 500
            cases.append(SyntheticCase(f"eval_{i}", amount))
        return cases

    def run_strategy(self, cases: List[SyntheticCase], strategy: str) -> Dict:
        gross_recovered = 0
        total_costs = 0
        success_count = 0
        total_actions = 0
        unnecessary_actions = 0
        
        for case in cases:
            recovered = False
            for attempt in range(self.max_attempts):
                # 1. Strategy decides whether to retry
                should_retry = False
                
                if strategy == "MAX_RETRY":
                    should_retry = True
                    
                elif strategy == "THRESHOLD":
                    should_retry = case.amount_paise >= 200000 # Only if >= ₹2000
                    
                elif strategy == "REVPILOT":
                    evals = self.engine.evaluate_case("FAILED_PAYMENT", case.amount_paise, attempt)
                    best_eval = evals[0] if evals else None
                    if best_eval and best_eval.final_enr > 0 and best_eval.action_type != "CLOSE_CASE":
                        should_retry = True
                
                if not should_retry:
                    break
                    
                # 2. Execute Action
                total_actions += 1
                total_costs += self.cost_per_attempt
                
                # 3. Check outcome
                attempt_penalty_factor = max(0.0, 1.0 - (attempt * 0.15))
                true_p = self.base_p * attempt_penalty_factor
                
                if case.success_rolls[attempt] <= true_p:
                    recovered = True
                    gross_recovered += case.amount_paise
                    success_count += 1
                    break
                else:
                    if strategy == "REVPILOT":
                        pass # It failed, loop continues to next attempt if ENR still > 0
                        
            if not recovered and total_actions > 0:
                unnecessary_actions += total_actions # Actions that didn't lead to recovery
                
        net_recovered = gross_recovered - total_costs
        
        return {
            "strategy": strategy,
            "gross_recovered": gross_recovered / 100,
            "total_costs": total_costs / 100,
            "net_recovered": net_recovered / 100,
            "recovery_rate": (success_count / len(cases)) * 100,
            "avg_actions_per_case": total_actions / len(cases)
        }

if __name__ == "__main__":
    evaluator = Evaluator()
    cases = evaluator.generate_cases(100, seed=42)
    
    results = []
    for strategy in ["MAX_RETRY", "THRESHOLD", "REVPILOT"]:
        res = evaluator.run_strategy(cases, strategy)
        results.append(res)
        
    print(f"\n{'STRATEGY':<15} | {'NET REC (INR)':<18} | {'GROSS (INR)':<15} | {'COSTS (INR)':<15} | {'REC RATE':<10} | {'AVG ACTIONS'}")
    print("-" * 95)
    for r in results:
        print(f"{r['strategy']:<15} | {r['net_recovered']:<18.2f} | {r['gross_recovered']:<15.2f} | {r['total_costs']:<15.2f} | {r['recovery_rate']:>5.1f}%    | {r['avg_actions_per_case']:.2f}")
    
    print("\nBenchmark reproducible using Seed=42.")
