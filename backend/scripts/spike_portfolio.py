from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app.economics.engine import ActionEvaluation

@dataclass
class PortfolioResult:
    selected_actions: List[Dict[str, Any]]
    skipped_cases: List[str]
    total_spend: int
    expected_net_recovery: int
    marginal_efficiency: float

class RecoveryPortfolioOptimizer:
    """
    Solves the Multiple-Choice Knapsack Problem (MCKP) for revenue recovery.
    Given a list of cases (each with candidate actions) and a total budget,
    selects at most one action per case to maximize total ENR without exceeding the budget.
    """
    
    def optimize(self, cases_dict: Dict[str, List[ActionEvaluation]], budget_paise: int) -> PortfolioResult:
        # Pre-process: for each case, filter out ENR <= 0 or cost > budget.
        # Include a "NO_ACTION" baseline (cost 0, ENR 0) for every case.
        
        # item_groups: list of (case_id, list_of_valid_actions)
        item_groups = []
        for case_id, evals in cases_dict.items():
            valid_actions = []
            for ev in evals:
                if ev.final_enr > 0 and ev.cost <= budget_paise:
                    valid_actions.append(ev)
            if valid_actions:
                item_groups.append((case_id, valid_actions))
                
        n = len(item_groups)
        
        # dp[w] stores the max ENR achievable with budget exactly w (or <= w depending on implementation)
        # To reconstruct the solution, we also need to store the choices.
        # choices[i][w] = the action index chosen for case i when budget is w.
        
        dp = [0] * (budget_paise + 1)
        # Store state transitions: states[i][w] = (prev_w, chosen_action_eval)
        # To save memory, we can just keep track of the DP table at each step.
        history = []
        
        for i in range(n):
            case_id, actions = item_groups[i]
            next_dp = list(dp) # Copy previous state (implicit NO_ACTION chosen)
            next_choice = [(w, None) for w in range(budget_paise + 1)] # Maps w -> (prev_w, action)
            
            for w in range(budget_paise + 1):
                # We can also choose NO_ACTION, which means next_dp[w] is at least dp[w]
                next_choice[w] = (w, None) 
                
            for action in actions:
                c = action.cost
                v = action.final_enr
                for w in range(budget_paise + 1):
                    if w >= c:
                        if dp[w - c] + v > next_dp[w]:
                            next_dp[w] = dp[w - c] + v
                            next_choice[w] = (w - c, action)
            
            dp = next_dp
            history.append(next_choice)
            
        # Find max ENR in the final dp table and its corresponding budget used
        max_enr = 0
        best_w = 0
        for w in range(budget_paise + 1):
            if dp[w] > max_enr:
                max_enr = dp[w]
                best_w = w
                
        # Backtrack to find chosen actions
        selected_actions = []
        curr_w = best_w
        for i in range(n - 1, -1, -1):
            prev_w, chosen_action = history[i][curr_w]
            if chosen_action is not None:
                selected_actions.append({
                    "case_id": item_groups[i][0],
                    "action": chosen_action
                })
            curr_w = prev_w
            
        # Identify skipped cases
        selected_case_ids = {item["case_id"] for item in selected_actions}
        skipped_cases = [case_id for case_id in cases_dict.keys() if case_id not in selected_case_ids]
        
        total_spend = best_w
        efficiency = (max_enr / total_spend) if total_spend > 0 else 0.0
        
        return PortfolioResult(
            selected_actions=selected_actions,
            skipped_cases=skipped_cases,
            total_spend=total_spend,
            expected_net_recovery=max_enr,
            marginal_efficiency=efficiency
        )

# Technical Spike / Benchmark
if __name__ == "__main__":
    from app.economics.engine import EconomicEngine
    
    print("Running Portfolio Optimizer Spike...")
    engine = EconomicEngine()
    
    # Generate 100 synthetic cases
    import random
    random.seed(42)
    
    cases_dict = {}
    total_unconstrained_spend = 0
    total_unconstrained_enr = 0
    
    for i in range(100):
        case_id = f"case_{i}"
        amount = random.randint(10, 5000) * 100 # INR 10 to INR 5,000
        history = random.choice([0.0, 0.5, 1.0])
        failures = random.randint(0, 3)
        
        evals = engine.evaluate_case(
            case_type="failed_payment",
            amount_at_risk=amount,
            attempt_count=1,
            age_days=0,
            failure_reason="insufficient_funds",
            customer_history_score=history,
            recent_30d_failures=failures
        )
        cases_dict[case_id] = evals
        
        # Track what the greedy unconstrained choice would be (what the current system does)
        best_action = evals[0]
        if best_action.final_enr > 0:
            total_unconstrained_spend += best_action.cost
            total_unconstrained_enr += best_action.final_enr

    print(f"\n[Unconstrained Baseline]")
    print(f"Total Cases: 100")
    print(f"Total Proposed Spend: INR {total_unconstrained_spend / 100:,.2f}")
    print(f"Total Expected Net Recovery (ENR): INR {total_unconstrained_enr / 100:,.2f}")
    
    # We constrain the budget to 30% of the unconstrained proposed spend
    budget_paise = int(total_unconstrained_spend * 0.3)
    print(f"\n[Constrained Target]")
    print(f"Recovery Budget: INR {budget_paise / 100:,.2f} (30% of baseline)")
    
    optimizer = RecoveryPortfolioOptimizer()
    
    start_time = time.time()
    result = optimizer.optimize(cases_dict, budget_paise)
    end_time = time.time()
    
    print(f"\n[Portfolio Optimization Result]")
    print(f"Compute Time: {(end_time - start_time) * 1000:.2f} ms")
    print(f"Selected Actions: {len(result.selected_actions)}")
    print(f"Skipped Cases: {len(result.skipped_cases)}")
    print(f"Budget Utilized: INR {result.total_spend / 100:,.2f} / INR {budget_paise / 100:,.2f}")
    print(f"Expected Net Recovery: INR {result.expected_net_recovery / 100:,.2f}")
    print(f"Net Recovery per INR 1 Spend: INR {result.marginal_efficiency:,.2f}")
    
    print(f"\n[Insight]")
    print(f"Unconstrained ENR/Spend: INR {(total_unconstrained_enr/total_unconstrained_spend) if total_unconstrained_spend else 0:,.2f}")
    print(f"Optimized ENR/Spend: INR {result.marginal_efficiency:,.2f}")
