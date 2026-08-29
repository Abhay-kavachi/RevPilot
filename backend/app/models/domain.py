from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean, CheckConstraint, Enum as SQLEnum, JSON, BigInteger
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.database.core import Base

class CaseStatus(str, enum.Enum):
    OPEN = "OPEN"
    ASSESSING = "ASSESSING"
    EXECUTING = "EXECUTING"
    WAITING_FOR_OUTCOME = "WAITING_FOR_OUTCOME"
    RECOVERED = "RECOVERED"
    STOPPED = "STOPPED"

class RevenueRiskCase(Base):
    __tablename__ = "revenue_risk_cases"
    
    id = Column(String(50), primary_key=True, index=True)
    customer_id = Column(String(50), index=True)
    customer_email = Column(String(255))
    customer_phone = Column(String(50))
    currency = Column(String(3), default="INR")
    case_type = Column(String(50), nullable=False) 
    status = Column(SQLEnum(CaseStatus), default=CaseStatus.OPEN)
    
    amount_at_risk = Column(BigInteger, nullable=False) # In paise
    amount_recovered = Column(BigInteger, default=0, nullable=False)
    
    attempt_count = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    recovery_deadline = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    __table_args__ = (
        CheckConstraint('amount_at_risk >= 0', name='check_amount_at_risk_positive'),
        CheckConstraint('amount_recovered >= 0', name='check_amount_recovered_positive'),
        CheckConstraint('attempt_count >= 0', name='check_attempt_count_positive'),
    )
    
    actions = relationship("CaseAction", back_populates="case")
    decisions = relationship("CaseDecision", back_populates="case")
    audit_events = relationship("AuditEvent", back_populates="case")

    def transition_to(self, new_status: CaseStatus):
        valid_transitions = {
            CaseStatus.OPEN: [CaseStatus.ASSESSING, CaseStatus.STOPPED],
            CaseStatus.ASSESSING: [CaseStatus.EXECUTING, CaseStatus.STOPPED],
            CaseStatus.EXECUTING: [CaseStatus.WAITING_FOR_OUTCOME, CaseStatus.STOPPED, CaseStatus.OPEN],
            CaseStatus.WAITING_FOR_OUTCOME: [CaseStatus.RECOVERED, CaseStatus.STOPPED, CaseStatus.OPEN],
            CaseStatus.RECOVERED: [],
            CaseStatus.STOPPED: []
        }
        if new_status not in valid_transitions[self.status]:
            raise ValueError(f"Invalid state transition from {self.status} to {new_status}")
        self.status = new_status

class CaseAction(Base):
    __tablename__ = "case_actions"
    
    id = Column(String(50), primary_key=True)
    case_id = Column(String(50), ForeignKey("revenue_risk_cases.id"), nullable=False)
    action_type = Column(String(50), nullable=False)
    
    idempotency_key = Column(String(100), unique=True)
    status = Column(String(50), default="PENDING") 
    
    provider_reference_id = Column(String(100))
    execution_result = Column(JSON)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    case = relationship("RevenueRiskCase", back_populates="actions")
    approvals = relationship("Approval", back_populates="action")

class CaseDecision(Base):
    __tablename__ = "case_decisions"
    
    id = Column(String(50), primary_key=True)
    case_id = Column(String(50), ForeignKey("revenue_risk_cases.id"), nullable=False)
    
    action_type = Column(String(50), nullable=False)
    expected_value = Column(BigInteger, nullable=False)
    success_probability = Column(Float, nullable=False)
    cost = Column(BigInteger, nullable=False)
    friction = Column(BigInteger, nullable=False)
    risk = Column(BigInteger, nullable=False)
    final_enr = Column(BigInteger, nullable=False)
    
    is_selected = Column(Boolean, default=False)
    policy_rejection_reason = Column(String(255))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        CheckConstraint('cost >= 0', name='check_decision_cost_positive'),
        CheckConstraint('friction >= 0', name='check_decision_friction_positive'),
        CheckConstraint('risk >= 0', name='check_decision_risk_positive'),
        CheckConstraint('success_probability >= 0.0 AND success_probability <= 1.0', name='check_decision_prob_bounds'),
    )
    
    case = relationship("RevenueRiskCase", back_populates="decisions")

class Approval(Base):
    __tablename__ = "approvals"
    
    id = Column(String(50), primary_key=True)
    action_id = Column(String(50), ForeignKey("case_actions.id"), nullable=False)
    status = Column(String(50), default="PENDING") 
    reviewer_id = Column(String(50))
    comments = Column(String(1000))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True))
    
    action = relationship("CaseAction", back_populates="approvals")

class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    
    event_id = Column(String(100), primary_key=True) 
    event_type = Column(String(100), nullable=False)
    payload = Column(JSON, nullable=False)
    processed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AuditEvent(Base):
    __tablename__ = "audit_events"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(String(50), ForeignKey("revenue_risk_cases.id"))
    event_type = Column(String(100), nullable=False)
    description = Column(String(1000))
    metadata_blob = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    case = relationship("RevenueRiskCase", back_populates="audit_events")

class PaymentReference(Base):
    __tablename__ = "payment_references"
    
    id = Column(String(50), primary_key=True)
    case_id = Column(String(50), ForeignKey("revenue_risk_cases.id"), nullable=False)
    reference_type = Column(String(50), nullable=False) 
    reference_id = Column(String(100), nullable=False, unique=True)
    status = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
