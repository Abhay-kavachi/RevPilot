from typing import List, Dict, Any
from dataclasses import dataclass
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
        item_groups = []
        for case_id, evals in cases_dict.items():
            valid_actions = []
            for ev in evals:
                if ev.final_enr > 0 and ev.cost <= budget_paise:
                    valid_actions.append(ev)
            if valid_actions:
                item_groups.append((case_id, valid_actions))
                
        n = len(item_groups)
        
        # dp[w] stores the max ENR achievable with budget exactly w (or <= w)
        dp = [0] * (budget_paise + 1)
        history = []
        
        for i in range(n):
            case_id, actions = item_groups[i]
            next_dp = list(dp) # Copy previous state (implicit NO_ACTION chosen)
            next_choice = [(w, None) for w in range(budget_paise + 1)] 
            
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
            
        max_enr = 0
        best_w = 0
        for w in range(budget_paise + 1):
            if dp[w] > max_enr:
                max_enr = dp[w]
                best_w = w
                
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
