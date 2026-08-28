from typing import List, Optional
from app.agent.schemas import AgentContext
from app.economics.engine import ActionEvaluation

class ActionSelector:
    def select_action(self, context: AgentContext, evaluations: List[ActionEvaluation]) -> Optional[str]:
        # Filter out ineligible actions based on policy constraints
        eligible_evaluations = [ev for ev in evaluations if self._check_policy(context, ev.action_type)]
        
        if not eligible_evaluations:
            return "CLOSE_CASE"
            
        # The evaluations are already sorted by ENR descending from the engine
        best_eval = eligible_evaluations[0]
        
        # If even the best action has negative or zero expected net revenue, STOP
        if best_eval.final_enr <= 0:
            return "CLOSE_CASE"
            
        return best_eval.action_type

    def _check_policy(self, context: AgentContext, action_type: str) -> bool:
        # 1. Max attempts boundary
        if context.attempt_count >= context.max_attempts and action_type != "CLOSE_CASE":
            return False
            
        # 2. Prevent repeating the exact same aggressive action immediately if it just failed 
        # (MVP simplification: we just rely on attempt count)
        
        return True
