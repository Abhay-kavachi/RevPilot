from typing import List
from app.economics.engine import EconomicEngine, ActionEvaluation
from app.agent.schemas import AgentContext

class AgentPlanner:
    def __init__(self):
        self.economic_engine = EconomicEngine()

    def plan_next_actions(self, context: AgentContext) -> List[ActionEvaluation]:
        # The planner delegates raw calculation to the deterministic engine
        evaluations = self.economic_engine.evaluate_case(
            case_type=context.case_type,
            amount_at_risk=context.amount_at_risk,
            attempt_count=context.attempt_count,
            age_days=context.days_since_creation,
            failure_reason=context.failure_reason,
            customer_history_score=context.customer_history_score
        )
        return evaluations
