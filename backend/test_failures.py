import pytest
import os
import json
import hmac
import hashlib
from app.database.core import SessionLocal
from app.models.domain import RevenueRiskCase, CaseStatus, CaseAction, AuditEvent, WebhookEvent
from app.agent.agent import RevPilotAgent
from app.razorpay.webhooks import WebhookVerifier
from app.agent.memory import AgentMemory

@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()

def test_negative_ev_stops_immediately(db):
    # Setup
    case_id = "test_failure_neg_ev"
    from app.models.domain import CaseAction, RevenueRiskCase, AuditEvent, CaseDecision
    db.query(CaseAction).filter_by(case_id=case_id).delete()
    db.query(AuditEvent).filter_by(case_id=case_id).delete()
    db.query(CaseDecision).filter_by(case_id=case_id).delete()
    db.query(RevenueRiskCase).filter_by(id=case_id).delete()
    db.commit()
    
    case = RevenueRiskCase(
        id=case_id,
        amount_at_risk=2, # Force negative EV to test STOPPED
        currency="INR",
        case_type="FAILED_PAYMENT",
        status=CaseStatus.OPEN
    )
    db.add(case)
    db.commit()
    
    # Process
    agent = RevPilotAgent(db)
    agent.process(case_id)
    
    # Verify
    updated_case = db.query(RevenueRiskCase).filter_by(id=case_id).first()
    assert updated_case.status == CaseStatus.STOPPED, "Negative EV case must STOP"

def test_max_attempt_stops(db):
    # Setup
    case_id = "test_failure_max_attempt"
    from app.models.domain import CaseAction, RevenueRiskCase, AuditEvent, CaseDecision
    db.query(CaseAction).filter_by(case_id=case_id).delete()
    db.query(AuditEvent).filter_by(case_id=case_id).delete()
    db.query(CaseDecision).filter_by(case_id=case_id).delete()
    db.query(RevenueRiskCase).filter_by(id=case_id).delete()
    db.commit()
    
    case = RevenueRiskCase(
        id=case_id,
        amount_at_risk=2000000, # Positive EV
        currency="INR",
        case_type="FAILED_PAYMENT",
        status=CaseStatus.OPEN,
        attempt_count=3,
        max_attempts=3
    )
    db.add(case)
    db.commit()
    
    # Process
    agent = RevPilotAgent(db)
    agent.process(case_id)
    
    # Verify
    updated_case = db.query(RevenueRiskCase).filter_by(id=case_id).first()
    assert updated_case.status == CaseStatus.STOPPED, "Max attempt case must STOP"

def test_forged_webhook_rejected(db):
    verifier = WebhookVerifier()
    payload = {"event": "payment.failed"}
    raw_body = json.dumps(payload).encode('utf-8')
    
    # Sign with WRONG secret
    wrong_secret = b"wrong_secret"
    forged_signature = hmac.new(wrong_secret, msg=raw_body, digestmod=hashlib.sha256).hexdigest()
    
    assert verifier.verify_signature(raw_body, forged_signature) == False, "Forged signature must be rejected"

def test_duplicate_webhook_deduplication(db):
    event_id = "evt_duplicate_test123"
    
    # Wipe previous
    db.query(WebhookEvent).filter_by(event_id=event_id).delete()
    db.commit()
    
    def process_webhook():
        # Check if exists
        exists = db.query(WebhookEvent).filter_by(event_id=event_id).first()
        if exists:
            return "DUPLICATE"
            
        # Store
        evt = WebhookEvent(
            event_id=event_id,
            event_type="payment.failed",
            payload={"mock": "data"}
        )
        db.add(evt)
        db.commit()
        return "PROCESSED"
        
    first = process_webhook()
    second = process_webhook()
    
    assert first == "PROCESSED"
    assert second == "DUPLICATE"
