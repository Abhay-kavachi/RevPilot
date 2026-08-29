from typing import List, Dict, Optional
from pydantic import BaseModel

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
    # Synthetic parameters mapping as per requirements. 
    # V = amount_at_risk, P = probability, C = action cost, F = friction, D = risk
    # ENR = (V * P) - C - F - D
    
    ACTION_PARAMS = {
        "FAILED_PAYMENT": {
            "RETRY_PAYMENT_OPPORTUNITY": {"P": 0.65, "C": 500, "F": 100, "D": 200},  # Configured in paise
            "CREATE_PAYMENT_LINK": {"P": 0.50, "C": 100, "F": 500, "D": 100},
            "SEND_REMINDER": {"P": 0.10, "C": 10, "F": 10, "D": 0},
            "LOG_ESCALATION": {"P": 0.05, "C": 1000, "F": 2000, "D": 0},
            "CLOSE_CASE": {"P": 0.0, "C": 0, "F": 0, "D": 0}, # STOP
        },
        "ABANDONED_CHECKOUT": {
            "CREATE_PAYMENT_LINK": {"P": 0.40, "C": 100, "F": 200, "D": 100},
            "SEND_REMINDER": {"P": 0.15, "C": 10, "F": 10, "D": 0},
            "LOG_ESCALATION": {"P": 0.0, "C": 1000, "F": 2000, "D": 0},
            "CLOSE_CASE": {"P": 0.0, "C": 0, "F": 0, "D": 0},
        },
        "OVERDUE_INVOICE": {
            "SEND_REMINDER": {"P": 0.30, "C": 10, "F": 100, "D": 0},
            "LOG_ESCALATION": {"P": 0.20, "C": 1000, "F": 500, "D": 500},
            "CLOSE_CASE": {"P": 0.0, "C": 0, "F": 0, "D": 0},
        }
    }

    def get_failure_reason_factor(self, reason: Optional[str]) -> float:
        if not reason:
            return 1.0
        reason = reason.upper()
        if "INSUFFICIENT_FUNDS" in reason:
            return 0.5 # Less likely to succeed quickly
        if "DECLINED_BY_BANK" in reason:
            return 0.7
        if "TIMEOUT" in reason or "NETWORK" in reason:
            return 0.95 # Highly recoverable
        return 1.0

    def evaluate_case(self, case_type: str, amount_at_risk: int, attempt_count: int, age_days: int = 0, failure_reason: Optional[str] = None, customer_history_score: float = 1.0) -> List[ActionEvaluation]:
        if case_type not in self.ACTION_PARAMS:
            return []
            
        params = self.ACTION_PARAMS[case_type]
        evaluations = []
        
        # Deterministic factors
        attempt_factor = max(0.1, 1.0 - (attempt_count * 0.15))
        age_factor = max(0.2, 1.0 - (age_days * 0.05))
        failure_reason_factor = self.get_failure_reason_factor(failure_reason)
        history_factor = customer_history_score
        
        for action_type, factors in params.items():
            if action_type == "CLOSE_CASE":
                evaluations.append(ActionEvaluation(
                    action_type=action_type,
                    expected_value=0,
                    success_probability=0.0,
                    cost=0,
                    friction=0,
                    risk=0,
                    final_enr=0
                ))
                continue
                
            base_p = factors["P"]
            
            # P(success) = base(action, case_type) * failure_reason_factor * attempt_factor * age_factor * history_factor
            p_success = base_p * failure_reason_factor * attempt_factor * age_factor * history_factor
            p_success = max(0.0, min(1.0, p_success)) # Bound between 0 and 1
            
            # Expected Value is V * P
            ev = int(amount_at_risk * p_success)
            c = factors["C"]
            f = factors["F"]
            d = factors["D"]
            
            enr = ev - c - f - d
            
            evaluations.append(ActionEvaluation(
                action_type=action_type,
                expected_value=ev,
                success_probability=p_success,
                cost=c,
                friction=f,
                risk=d,
                final_enr=enr
            ))
            
        # Sort descending by ENR
        evaluations.sort(key=lambda e: e.final_enr, reverse=True)
        return evaluations
