import json
import os
from typing import Dict, Any, List
from pydantic import BaseModel, StrictInt

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
    action_costs_paise: Dict[str, StrictInt]
    action_frictions_paise: Dict[str, StrictInt]
    action_risks_paise: Dict[str, StrictInt]
    
    def get_base_probability(self, action_type: str) -> float:
        if action_type not in self.base_probabilities:
            raise KeyError(f"Missing base probability for action: {action_type}")
        return self.base_probabilities[action_type]
        
    def get_failure_reason_multiplier(self, reason: str) -> float:
        # Require explicit definitions in policy, e.g., 'unknown'
        if reason not in self.failure_reason_multipliers:
            raise KeyError(f"Missing multiplier for failure reason: {reason}")
        return self.failure_reason_multipliers[reason]
        
    def get_attempt_multiplier(self, attempt_count: int) -> float:
        if not self.attempt_adjustments:
            raise ValueError("attempt_adjustments cannot be empty")
        # Assumes sorted by attempt_count asc
        for adj in reversed(self.attempt_adjustments):
            if attempt_count >= adj.attempt_count:
                return adj.multiplier
        raise ValueError(f"No attempt adjustment matches attempt_count: {attempt_count}")
        
    def get_age_multiplier(self, age_days: int) -> float:
        if not self.age_adjustments:
            raise ValueError("age_adjustments cannot be empty")
        # Assumes sorted by max_days asc
        for adj in self.age_adjustments:
            if age_days <= adj.max_days:
                return adj.multiplier
        return self.age_adjustments[-1].multiplier

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
