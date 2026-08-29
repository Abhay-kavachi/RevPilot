import asyncio
import uuid
import sys
from app.database.core import SessionLocal
from app.models.domain import RevenueRiskCase, CaseStatus, CaseAction
from app.agent.agent import RevPilotAgent
from app.razorpay.adapter import RazorpayAdapter
from app.core.config import settings

def run():
    print("Starting REAL E2E Recovery Case...")
    
    db = SessionLocal()
    case_id = str(uuid.uuid4())
    
    # Let's use an amount that allows us to do a partial payment test.
    # We will set amount_at_risk = 50000 (Rs 500)
    # The user can choose to pay only Rs 200 via the Razorpay test page if it supports partial payment.
    # Wait, Payment Links generally enforce full payment unless "accept_partial" is true.
    # By default, Razorpay payment links don't accept partial payments unless specified.
    # Let's check adapter.py. It does not set accept_partial.
    # To test partial payments, we must set "accept_partial": True in the link!
    
    case = RevenueRiskCase(
        id=case_id,
        amount_at_risk=50000, # 500 INR
        amount_recovered=0,
        case_type="FAILED_PAYMENT",
        status=CaseStatus.OPEN
    )
    db.add(case)
    db.commit()
    print(f"Created Case: {case_id}")
    
    # Run agent
    agent = RevPilotAgent(db)
    agent.process(case_id)
    
    db.refresh(case)
    print(f"Case status after agent execution: {case.status}")
    
    action = db.query(CaseAction).filter_by(case_id=case_id).first()
    if action:
        print(f"Action created: {action.action_type}")
        print(f"Provider Ref ID: {action.provider_reference_id}")
        print(f"Idempotency Key: {action.idempotency_key}")
        
        # Unfortunately, RevPilotAgent does not save the short_url to the DB right now.
        # But we can query Razorpay using the provider_reference_id to get the link!
        
        import httpx
        url = f"{settings.razorpay.API_BASE_URL}/payment_links/{action.provider_reference_id}"
        resp = httpx.get(url, auth=(settings.razorpay.KEY_ID, settings.razorpay.KEY_SECRET))
        if resp.status_code == 200:
            link_data = resp.json()
            short_url = link_data.get("short_url")
            print(f"\n=========================================")
            print(f"PAYMENT LINK URL: {short_url}")
            print(f"=========================================\n")
            
            # To test partial payments, wait, can we update the link? No.
            # Did the adapter set accept_partial? No. So it will be full payment.
            # I will just write this output and ask the user to pay it.
            
    db.close()

if __name__ == "__main__":
    run()
