from typing import List, Dict, Optional, Any
from pydantic import BaseModel
from app.core.policy import policy_manager

class ActionEvaluation(BaseModel):
    action_type: str
    expected_value: int
    success_probability: float
    cost: int
    friction: int
    risk: int
    final_enr: int
    is_eligible: bool = True

class EconomicEngine:
    """
    Evaluates potential actions using expected value (ENR) calculations, driven entirely by configuration.
    Zero business rules are hardcoded here.
    """
    def __init__(self):
        self.policy = policy_manager.economic_policy
        self.recovery = policy_manager.recovery_policy

    def evaluate_case(self, case_type: str, amount_at_risk: int, attempt_count: int, age_days: int = 0, failure_reason: Optional[str] = None, customer_history_score: float = 1.0) -> List[ActionEvaluation]:
        if not (0.0 <= customer_history_score <= 1.0):
            raise ValueError(f"customer_history_score must be between 0 and 1, got {customer_history_score}")
            
        evaluations = []
        
        for action in self.recovery.allowed_actions:
            if action == "CLOSE_CASE" or action == "NO_ACTION":
                evaluations.append(ActionEvaluation(
                    action_type=action, expected_value=0, success_probability=0.0, cost=0, friction=0, risk=0, final_enr=0
                ))
                continue
                
            # 1. Fetch base configs from policy
            base_prob = self.policy.get_base_probability(action)
            cost = self.policy.action_costs_paise.get(action)
            friction = self.policy.action_frictions_paise.get(action)
            risk = self.policy.action_risks_paise.get(action)
            
            if cost is None or friction is None or risk is None:
                raise KeyError(f"Missing monetary configuration for action {action}")
            
            # 2. Apply deterministic state-aware multipliers from policy
            reason_factor = self.policy.get_failure_reason_multiplier(failure_reason or "unknown")
            attempt_factor = self.policy.get_attempt_multiplier(attempt_count)
            age_factor = self.policy.get_age_multiplier(age_days)
            history_factor = customer_history_score
            
            # 3. Calculate final bounded probability
            p_success = base_prob * reason_factor * attempt_factor * age_factor * history_factor
            p_success = max(0.0, min(1.0, p_success)) # Technical invariant: Probability bounds
            
            # 4. Calculate Net Expected Value (EV)
            ev = int(amount_at_risk * p_success)
            enr = ev - cost - friction - risk
            
            evaluations.append(ActionEvaluation(
                action_type=action,
                expected_value=ev,
                success_probability=p_success,
                cost=cost,
                friction=friction,
                risk=risk,
                final_enr=enr
            ))
            
        return sorted(evaluations, key=lambda x: x.final_enr, reverse=True)
