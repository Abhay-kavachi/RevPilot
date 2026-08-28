import sys
import os
import httpx
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database.core import SessionLocal
from app.models.domain import RevenueRiskCase, CaseStatus, CaseAction, CaseDecision, AuditEvent, WebhookEvent
from app.agent.agent import RevPilotAgent

def run_demo_setup():
    db = SessionLocal()
    try:
        # Wipe database
        db.query(CaseAction).delete()
        db.query(CaseDecision).delete()
        db.query(AuditEvent).delete()
        db.query(WebhookEvent).delete()
        db.query(RevenueRiskCase).delete()
        db.commit()
        
        # 1. Failed Payment - Positive EV
        c1 = RevenueRiskCase(
            id="demo_failed_pos",
            amount_at_risk=2000000, # 20k INR
            currency="INR",
            case_type="FAILED_PAYMENT",
            status=CaseStatus.OPEN,
            attempt_count=0,
            max_attempts=3
        )
        
        # 2. Failed Payment - Negative EV (e.g. tiny amount)
        c2 = RevenueRiskCase(
            id="demo_failed_neg",
            amount_at_risk=200, # 2 INR
            currency="INR",
            case_type="FAILED_PAYMENT",
            status=CaseStatus.OPEN,
            attempt_count=0,
            max_attempts=3
        )
        
        db.add(c1)
        db.add(c2)
        db.commit()
        
        # Process them via Agent!
        agent = RevPilotAgent(db)
        print("Running agent for Positive EV case (should CREATE_PAYMENT_LINK/RETRY)")
        agent.process("demo_failed_pos")
        
        print("\nRunning agent for Negative EV case (should STOP)")
        agent.process("demo_failed_neg")
        
        print("\nDemo setup complete! Open demo/dashboard.html in your browser.")
        
    finally:
        db.close()

if __name__ == "__main__":
    run_demo_setup()
