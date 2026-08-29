import json
import os
from typing import Dict, Any, List
from pydantic import BaseModel

class AttemptAdjustment(BaseModel):
    attempt_count: int
    multiplier: float

class AgeAdjustment(BaseModel):
    max_days: int
    multiplier: float

class EconomicPolicy(BaseModel):
    version: str
    base_probabilities: Dict[str, float]
    failure_reason_multipliers: Dict[str, float]
    attempt_adjustments: List[AttemptAdjustment]
    age_adjustments: List[AgeAdjustment]
    action_costs: Dict[str, float]
    action_frictions: Dict[str, float]
    action_risks: Dict[str, float]
    
    def get_base_probability(self, action_type: str) -> float:
        return self.base_probabilities.get(action_type, 0.0)
        
    def get_failure_reason_multiplier(self, reason: str) -> float:
        return self.failure_reason_multipliers.get(reason, 1.0)
        
    def get_attempt_multiplier(self, attempt_count: int) -> float:
        # Assumes sorted by attempt_count asc
        for adj in reversed(self.attempt_adjustments):
            if attempt_count >= adj.attempt_count:
                return adj.multiplier
        return 1.0
        
    def get_age_multiplier(self, age_days: int) -> float:
        # Assumes sorted by max_days asc
        for adj in self.age_adjustments:
            if age_days <= adj.max_days:
                return adj.multiplier
        # Fallback for oldest cases
        return self.age_adjustments[-1].multiplier if self.age_adjustments else 1.0

class RecoveryPolicy(BaseModel):
    version: str
    max_attempts: int
    min_expected_value: float
    allowed_actions: List[str]
    stop_threshold: float

class PolicyManager:
    def __init__(self, policy_path: str = None):
        if not policy_path:
            policy_path = os.path.join(os.path.dirname(__file__), "..", "..", "policy.json")
            
        with open(policy_path, "r") as f:
            data = json.load(f)
            
        self.economic_policy = EconomicPolicy(**data.get("economic_policy", {}))
        self.recovery_policy = RecoveryPolicy(**data.get("recovery_policy", {}))

# Singleton instance
policy_manager = PolicyManager()
