from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean, CheckConstraint, Enum as SQLEnum, JSON, BigInteger
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.database.core import Base
from app.core.config import settings

L = settings.limits

class CaseStatus(str, enum.Enum):
    OPEN = "OPEN"
    ASSESSING = "ASSESSING"
    EXECUTING = "EXECUTING"
    WAITING_FOR_OUTCOME = "WAITING_FOR_OUTCOME"
    RECOVERED = "RECOVERED"
    STOPPED = "STOPPED"

class RevenueRiskCase(Base):
    __tablename__ = "revenue_risk_cases"
    
    id = Column(String(L.ID_MAX_LENGTH), primary_key=True, index=True)
    merchant_id = Column(String(L.ID_MAX_LENGTH), index=True, nullable=True) # Supports multi-tenancy
    customer_id = Column(String(L.ID_MAX_LENGTH), index=True)
    customer_email = Column(String(L.EMAIL_MAX_LENGTH))
    customer_phone = Column(String(L.PHONE_MAX_LENGTH))
    currency = Column(String(L.CURRENCY_MAX_LENGTH), default="INR")
    case_type = Column(String(L.ID_MAX_LENGTH), nullable=False) 
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
            from app.core.errors import ErrorCode
            raise ValueError(f"{ErrorCode.INVALID_STATE_TRANSITION}: from {self.status} to {new_status}")
        self.status = new_status

class CaseAction(Base):
    __tablename__ = "case_actions"
    
    id = Column(String(L.ID_MAX_LENGTH), primary_key=True)
    case_id = Column(String(L.ID_MAX_LENGTH), ForeignKey("revenue_risk_cases.id"), nullable=False)
    action_type = Column(String(L.ID_MAX_LENGTH), nullable=False)
    
    idempotency_key = Column(String(L.REFERENCE_MAX_LENGTH), unique=True)
    status = Column(String(L.ID_MAX_LENGTH), default="PENDING") 
    
    provider_reference_id = Column(String(L.REFERENCE_MAX_LENGTH))
    execution_result = Column(JSON)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    case = relationship("RevenueRiskCase", back_populates="actions")
    approvals = relationship("Approval", back_populates="action")

class CaseDecision(Base):
    __tablename__ = "case_decisions"
    
    id = Column(String(L.ID_MAX_LENGTH), primary_key=True)
    case_id = Column(String(L.ID_MAX_LENGTH), ForeignKey("revenue_risk_cases.id"), nullable=False)
    
    action_type = Column(String(L.ID_MAX_LENGTH), nullable=False)
    expected_value = Column(BigInteger, nullable=False)
    success_probability = Column(Float, nullable=False)
    cost = Column(BigInteger, nullable=False)
    friction = Column(BigInteger, nullable=False)
    risk = Column(BigInteger, nullable=False)
    final_enr = Column(BigInteger, nullable=False)
    
    is_selected = Column(Boolean, default=False)
    policy_rejection_reason = Column(String(L.EMAIL_MAX_LENGTH))
    
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
    
    id = Column(String(L.ID_MAX_LENGTH), primary_key=True)
    action_id = Column(String(L.ID_MAX_LENGTH), ForeignKey("case_actions.id"), nullable=False)
    status = Column(String(L.ID_MAX_LENGTH), default="PENDING") 
    reviewer_id = Column(String(L.ID_MAX_LENGTH))
    comments = Column(String(L.DESCRIPTION_MAX_LENGTH))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True))
    
    action = relationship("CaseAction", back_populates="approvals")

class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    
    event_id = Column(String(L.REFERENCE_MAX_LENGTH), primary_key=True) 
    event_type = Column(String(L.REFERENCE_MAX_LENGTH), nullable=False)
    payload = Column(JSON, nullable=False)
    processed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AuditEvent(Base):
    __tablename__ = "audit_events"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(String(L.ID_MAX_LENGTH), ForeignKey("revenue_risk_cases.id"))
    event_type = Column(String(L.REFERENCE_MAX_LENGTH), nullable=False)
    description = Column(String(L.DESCRIPTION_MAX_LENGTH))
    metadata_blob = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    case = relationship("RevenueRiskCase", back_populates="audit_events")

class PaymentReference(Base):
    __tablename__ = "payment_references"
    
    id = Column(String(L.ID_MAX_LENGTH), primary_key=True)
    case_id = Column(String(L.ID_MAX_LENGTH), ForeignKey("revenue_risk_cases.id"), nullable=False)
    reference_type = Column(String(L.ID_MAX_LENGTH), nullable=False) 
    reference_id = Column(String(L.REFERENCE_MAX_LENGTH), nullable=False, unique=True)
    status = Column(String(L.ID_MAX_LENGTH))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
