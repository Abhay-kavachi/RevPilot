from sqlalchemy.orm import Session
from app.agent.memory import AgentMemory
from app.agent.planner import AgentPlanner
from app.agent.action_selector import ActionSelector
from app.models.domain import CaseStatus
from app.razorpay.adapter import RazorpayAdapter
import uuid

class ExecutionLoop:
    def __init__(self, db: Session):
        self.db = db
        self.memory = AgentMemory(db)
        self.planner = AgentPlanner()
        self.selector = ActionSelector()
        self.adapter = RazorpayAdapter()

    def process_case(self, case_id: str):
        # 1. OBSERVE & UNDERSTAND: Build context
        context = self.memory.build_context(case_id)
        
        if not context.is_recoverable:
            print(f"Case {case_id} is no longer recoverable. Current status: {context.status}")
            return
            
        # Update state to ASSESSING
        self.memory.update_case_status(case_id, CaseStatus.ASSESSING)

        # 2. EVALUATE: Calculate action values
        evaluations = self.planner.plan_next_actions(context)
        
        # 3. CHOOSE & CHECK POLICY: Enforce policy and select best action
        selected_action = self.selector.select_action(context, evaluations)
        
        # 4. Record decisions
        self.memory.record_decisions(case_id, evaluations, selected_action)
        
        # 5. EXECUTE or STOP
        if selected_action == "CLOSE_CASE":
            print(f"Agent chose to STOP processing case {case_id}")
            self.memory.update_case_status(case_id, CaseStatus.STOPPED)
            return
            
        # Transition to EXECUTING
        self.memory.update_case_status(case_id, CaseStatus.EXECUTING)
        
        # Dispatch action
        idempotency_key = f"case_{case_id}_action_{selected_action}_attempt_{context.attempt_count}"
        
        provider_ref = None
        if selected_action in ["CREATE_PAYMENT_LINK", "RETRY_PAYMENT_OPPORTUNITY"]:
            # Real call to Razorpay (requires valid test keys, else httpx will 401)
            # For MS4 we want this to work. If auth is mock, it will fail gracefully.
            success, response = self.adapter.create_payment_link(
                amount=context.amount_at_risk,
                currency="INR",
                reference_id=idempotency_key,
                description=f"Recovery payment for case {case_id}"
            )
            if success:
                provider_ref = response.get("id")
            else:
                print(f"Failed to create Payment Link: {response}")
                # We still record the action as failed
        
        # Record the action
        action_id = self.memory.record_action_created(case_id, selected_action, idempotency_key)
        if provider_ref:
            self.memory.update_action_provider_ref(action_id, provider_ref)
        
        # Transition to WAITING_FOR_OUTCOME (Wait for webhook)
        self.memory.update_case_status(case_id, CaseStatus.WAITING_FOR_OUTCOME)
        print(f"Agent dispatched {selected_action} for case {case_id}. Provider Ref: {provider_ref}")
