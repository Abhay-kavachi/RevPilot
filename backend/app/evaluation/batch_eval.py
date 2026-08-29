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
        self.success_rolls = [random.random() for _ in range(5)]
        
class WorldModel:
    """Independent simulation environment. Hidden ground-truth mechanics."""
    def __init__(self):
        # The real world has slightly different probabilities than the agent believes
        self.true_base_p = 0.58  # Agent believes 0.65
        self.true_c = 500
        self.true_f = 120        # Agent believes 100
        self.true_d = 250        # Agent believes 200
        self.true_cost_per_attempt = self.true_c + self.true_f + self.true_d

    def simulate_outcome(self, attempt: int, roll: float) -> bool:
        # Real world decay is steeper than agent believes (0.2 instead of 0.15)
        true_attempt_penalty_factor = max(0.0, 1.0 - (attempt * 0.20))
        true_p = self.true_base_p * true_attempt_penalty_factor
        return roll <= true_p
        
class Evaluator:
    def __init__(self):
        self.engine = EconomicEngine()
        self.world = WorldModel()
        self.max_attempts = 3

    def generate_cases(self, count: int, seed: int = 42) -> List[SyntheticCase]:
        random.seed(seed)
        cases = []
        for i in range(count):
            if i < count // 3:
                # Micro-transactions
                amount = random.randint(1, 15) * 100
            else:
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
        stop_accuracy_num = 0
        stop_accuracy_den = 0
        
        for case in cases:
            recovered = False
            case_actions = 0
            for attempt in range(self.max_attempts):
                should_retry = False
                
                if strategy == "MAX_RETRY":
                    should_retry = True
                elif strategy == "REVPILOT":
                    evals = self.engine.evaluate_case("FAILED_PAYMENT", case.amount_paise, attempt, age_days=0, failure_reason="DECLINED_BY_BANK")
                    best_eval = evals[0] if evals else None
                    if best_eval and best_eval.final_enr > 0 and best_eval.action_type != "CLOSE_CASE":
                        should_retry = True
                
                if not should_retry:
                    # Record stop accuracy: Did it correctly stop on negative EV?
                    # True EV: P(true) * V - true_cost
                    true_p = self.world.true_base_p * max(0.0, 1.0 - (attempt * 0.20))
                    true_ev = (true_p * case.amount_paise) - self.world.true_cost_per_attempt
                    stop_accuracy_den += 1
                    if true_ev < 0:
                        stop_accuracy_num += 1
                    break
                    
                total_actions += 1
                case_actions += 1
                total_costs += self.world.true_cost_per_attempt
                
                if self.world.simulate_outcome(attempt, case.success_rolls[attempt]):
                    recovered = True
                    gross_recovered += case.amount_paise
                    success_count += 1
                    break
                        
            if not recovered and case_actions > 0:
                unnecessary_actions += case_actions 
                
        net_recovered = gross_recovered - total_costs
        
        return {
            "strategy": strategy,
            "gross_recovered": gross_recovered / 100,
            "total_costs": total_costs / 100,
            "net_recovered": net_recovered / 100,
            "recovery_rate": (success_count / len(cases)) * 100,
            "avg_actions_per_case": total_actions / len(cases),
            "unnecessary_actions": unnecessary_actions,
            "stop_accuracy": (stop_accuracy_num / stop_accuracy_den * 100) if stop_accuracy_den > 0 else 100.0
        }

import subprocess

def get_git_commit():
    try:
        return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()
    except Exception:
        return "unknown"

if __name__ == "__main__":
    from app.core.policy import policy_manager
    evaluator = Evaluator()
    seeds = [42, 100, 999, 12345, 55555]
    
    commit_sha = get_git_commit()
    policy_version = policy_manager.economic_policy.version
    
    print("=" * 60)
    print("REPRODUCIBILITY METADATA")
    print(f"Dataset Version: v1.0 (Synthetic)")
    print(f"World Model Version: v1.0.0")
    print(f"Economic Policy Version: {policy_version}")
    print(f"Code Commit SHA: {commit_sha}")
    print("=" * 60)
    
    print("\nRunning multi-seed independent benchmark...")
    for seed in seeds:
        print(f"\nSEED: {seed}")
        cases = evaluator.generate_cases(100, seed=seed)
        
        results = []
        for strategy in ["MAX_RETRY", "REVPILOT"]:
            res = evaluator.run_strategy(cases, strategy)
            results.append(res)
            
        print(f"{'STRATEGY':<15} | {'NET REC (INR)':<18} | {'GROSS (INR)':<15} | {'COSTS (INR)':<15} | {'REC RATE':<10} | {'AVG ACTIONS':<15} | {'STOP ACCURACY'}")
        print("-" * 110)
        for r in results:
            print(f"{r['strategy']:<15} | {r['net_recovered']:<18.2f} | {r['gross_recovered']:<15.2f} | {r['total_costs']:<15.2f} | {r['recovery_rate']:>5.1f}%    | {r['avg_actions_per_case']:<15.2f} | {r['stop_accuracy']:.1f}%")
