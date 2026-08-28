import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database.core import SessionLocal
from app.models.domain import RevenueRiskCase, CaseStatus, CaseAction, CaseDecision, AuditEvent
from app.agent.agent import RevPilotAgent

def setup_test_cases(db):
    # Wipe previous test data
    for case_id in ["case_agent_test_pos", "case_agent_test_neg"]:
        db.query(CaseAction).filter_by(case_id=case_id).delete()
        db.query(CaseDecision).filter_by(case_id=case_id).delete()
        db.query(AuditEvent).filter_by(case_id=case_id).delete()
        db.query(RevenueRiskCase).filter_by(id=case_id).delete()
    db.commit()
    
    # Case 1: Positive EV
    c1 = RevenueRiskCase(
        id="case_agent_test_pos",
        amount_at_risk=2000000, # 20k INR
        currency="INR",
        case_type="FAILED_PAYMENT",
        status=CaseStatus.OPEN,
        attempt_count=0,
        max_attempts=3
    )
    
    # Case 2: Negative EV
    c2 = RevenueRiskCase(
        id="case_agent_test_neg",
        amount_at_risk=100, # 1 INR
        currency="INR",
        case_type="FAILED_PAYMENT",
        status=CaseStatus.OPEN,
        attempt_count=0,
        max_attempts=3
    )
    
    db.merge(c1)
    db.merge(c2)
    db.commit()

def run_tests():
    db = SessionLocal()
    try:
        setup_test_cases(db)
        
        agent = RevPilotAgent(db)
        
        print("\n--- Running Agent for Positive EV Case ---")
        agent.process("case_agent_test_pos")
        
        print("\n--- Running Agent for Negative EV Case ---")
        agent.process("case_agent_test_neg")
        
        # Verify DB states
        c1 = db.query(RevenueRiskCase).filter_by(id="case_agent_test_pos").first()
        c2 = db.query(RevenueRiskCase).filter_by(id="case_agent_test_neg").first()
        
        print("\n--- Final DB States ---")
        print(f"Positive Case Status: {c1.status.value}")
        print(f"Negative Case Status: {c2.status.value}")
        
    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
