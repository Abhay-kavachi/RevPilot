from typing import List, Dict
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

    def evaluate_case(self, case_type: str, amount_at_risk: int, attempt_count: int) -> List[ActionEvaluation]:
        if case_type not in self.ACTION_PARAMS:
            return []
            
        params = self.ACTION_PARAMS[case_type]
        evaluations = []
        
        # Diminishing returns penalty per attempt
        attempt_penalty_factor = max(0.0, 1.0 - (attempt_count * 0.15))
        
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
                
            p_success = factors["P"] * attempt_penalty_factor
            
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
