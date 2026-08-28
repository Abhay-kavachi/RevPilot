from sqlalchemy.orm import Session
from app.models.domain import RevenueRiskCase, CaseAction, CaseDecision, AuditEvent, CaseStatus
from app.agent.schemas import AgentContext, ActionHistory
import uuid

class AgentMemory:
    def __init__(self, db: Session):
        self.db = db

    def build_context(self, case_id: str) -> AgentContext:
        case = self.db.query(RevenueRiskCase).filter(RevenueRiskCase.id == case_id).first()
        if not case:
            raise ValueError(f"Case {case_id} not found")
            
        history = []
        for action in case.actions:
            history.append(ActionHistory(
                action_type=action.action_type,
                status=action.status,
                created_at=action.created_at,
                execution_result=action.execution_result
            ))
            
        is_recoverable = case.status not in [CaseStatus.RECOVERED, CaseStatus.STOPPED, CaseStatus.ESCALATED]
            
        return AgentContext(
            case_id=case.id,
            case_type=case.case_type,
            status=case.status,
            amount_at_risk=case.amount_at_risk,
            attempt_count=case.attempt_count,
            max_attempts=case.max_attempts,
            recovery_deadline=case.recovery_deadline,
            action_history=history,
            is_recoverable=is_recoverable
        )

    def record_decisions(self, case_id: str, evaluations: list, selected_action_type: str):
        for ev in evaluations:
            decision = CaseDecision(
                id=f"dec_{uuid.uuid4().hex[:12]}",
                case_id=case_id,
                action_type=ev.action_type,
                expected_value=ev.expected_value,
                success_probability=ev.success_probability,
                cost=ev.cost,
                friction=ev.friction,
                risk=ev.risk,
                final_enr=ev.final_enr,
                is_selected=(ev.action_type == selected_action_type)
            )
            self.db.add(decision)
        
        audit = AuditEvent(
            case_id=case_id,
            event_type="DECISION_MADE",
            description=f"Agent evaluated options and selected {selected_action_type}",
            metadata_blob={"selected": selected_action_type, "options": len(evaluations)}
        )
        self.db.add(audit)
        self.db.commit()

    def update_case_status(self, case_id: str, new_status: CaseStatus):
        case = self.db.query(RevenueRiskCase).filter(RevenueRiskCase.id == case_id).first()
        if case:
            case.status = new_status
            
            audit = AuditEvent(
                case_id=case_id,
                event_type="STATUS_CHANGED",
                description=f"Case status changed to {new_status.value}",
                metadata_blob={"new_status": new_status.value}
            )
            self.db.add(audit)
            self.db.commit()
            
    def increment_attempt(self, case_id: str):
        case = self.db.query(RevenueRiskCase).filter(RevenueRiskCase.id == case_id).first()
        if case:
            case.attempt_count += 1
            self.db.commit()

    def record_action_created(self, case_id: str, action_type: str, idempotency_key: str):
        action = CaseAction(
            id=f"act_{uuid.uuid4().hex[:12]}",
            case_id=case_id,
            action_type=action_type,
            status="PENDING",
            idempotency_key=idempotency_key
        )
        self.db.add(action)
        
        audit = AuditEvent(
            case_id=case_id,
            event_type="ACTION_DISPATCHED",
            description=f"Dispatched action {action_type}",
            metadata_blob={"action_id": action.id, "type": action_type}
        )
        self.db.add(audit)
        
        # Also increment the attempt count
        case = self.db.query(RevenueRiskCase).filter(RevenueRiskCase.id == case_id).first()
        if case:
            case.attempt_count += 1
            
        self.db.commit()
        return action.id
        
    def update_action_provider_ref(self, action_id: str, provider_ref: str):
        action = self.db.query(CaseAction).filter(CaseAction.id == action_id).first()
        if action:
            action.provider_reference_id = provider_ref
            self.db.commit()
