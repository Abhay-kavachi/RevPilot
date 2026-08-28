from sqlalchemy import Column, String, Integer, BigInteger, Boolean, DateTime, ForeignKey, Enum as SQLEnum, JSON, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from app.database.core import Base

class CaseStatus(str, enum.Enum):
    OPEN = "OPEN"
    ASSESSING = "ASSESSING"
    EXECUTING = "EXECUTING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    WAITING_FOR_OUTCOME = "WAITING_FOR_OUTCOME"
    RECOVERED = "RECOVERED"
    ESCALATED = "ESCALATED"
    STOPPED = "STOPPED"

class RevenueRiskCase(Base):
    __tablename__ = "revenue_risk_cases"
    
    id = Column(String(50), primary_key=True)
    amount_at_risk = Column(BigInteger, nullable=False) # In paise
    currency = Column(String(3), default="INR")
    case_type = Column(String(50), nullable=False) 
    status = Column(SQLEnum(CaseStatus), default=CaseStatus.OPEN)
    
    customer_id = Column(String(50))
    customer_email = Column(String(255))
    customer_phone = Column(String(50))
    
    attempt_count = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    recovery_deadline = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    actions = relationship("CaseAction", back_populates="case")
    decisions = relationship("CaseDecision", back_populates="case")
    audit_events = relationship("AuditEvent", back_populates="case")

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
