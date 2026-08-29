import pytest
import asyncio
import uuid
import json
from sqlalchemy.orm import Session
from app.database.core import SessionLocal
from app.models.domain import RevenueRiskCase, CaseStatus, CaseAction
from app.agent.agent import RevPilotAgent
from app.api.endpoints import razorpay_webhook
from test_webhook_integrity import MockRequest, sign_payload

# Since SQLite locks the whole DB often when writing, 
# testing 10 true concurrent threads might just throw Database is locked on SQLite.
# But RevPilot is required to use PostgreSQL for this phase, so this is valid.

def concurrent_agent_worker(case_id: str):
    db = SessionLocal()
    try:
        agent = RevPilotAgent(db)
        # Process the case (includes check-then-act)
        agent.process(case_id)
    except Exception as e:
        print(f"Worker exception (expected if collision handled by locking): {e}")
    finally:
        db.close()

@pytest.mark.asyncio
async def test_concurrency_and_replay_resilience():
    # Setup
    db = SessionLocal()
    case_id = str(uuid.uuid4())
    case = RevenueRiskCase(
        id=case_id,
        amount_at_risk=10000,
        amount_recovered=0,
        case_type="FAILED_PAYMENT",
        status=CaseStatus.OPEN
    )
    db.add(case)
    db.commit()
    db.close()

    print(f"\n--- Starting 10 concurrent agent processing attempts for case {case_id} ---")
    
    # Run 10 concurrent requests using asyncio.to_thread
    tasks = [
        asyncio.to_thread(concurrent_agent_worker, case_id)
        for _ in range(10)
    ]
    await asyncio.gather(*tasks, return_exceptions=True)
    
    db = SessionLocal()
    case = db.query(RevenueRiskCase).get(case_id)
    
    actions = db.query(CaseAction).filter(CaseAction.case_id == case_id).all()
    print(f"Resulting actions created: {len(actions)}")
    
    # Assert ONE logical action
    # Wait, the RevPilotAgent doesn't use SELECT FOR UPDATE in SQLite, but we use Postgres now!
    # Wait, did we actually implement SELECT FOR UPDATE in agent.py?
    # execution_loop.py does `context = self.memory.build_context(case_id)`
    # If it's not locked, it might create 10 actions!
    
    # We must ensure there's exactly 1 action!
    assert len(actions) == 1, f"Expected 1 action, got {len(actions)}. Concurrency protection failed!"
    
    action = actions[0]
    
    print(f"\n--- Starting 10 concurrent webhook replays ---")
    payload = {
        "event": "payment_link.paid",
        "id": f"evt_{uuid.uuid4()}",
        "payload": {"payment_link": {"entity": {"reference_id": action.idempotency_key, "amount_paid": 10000}}}
    }
    
    body_bytes, expected_sig = sign_payload(payload)
    
    # Send 10 concurrent webhooks
    async def fire_webhook():
        w_db = SessionLocal()
        req = MockRequest(body_bytes, {
            "x-razorpay-signature": expected_sig,
            "x-razorpay-event-id": payload["id"]
        })
        try:
            res = await razorpay_webhook(req, w_db)
            return res
        finally:
            w_db.close()
            
    wh_tasks = [fire_webhook() for _ in range(10)]
    results = await asyncio.gather(*wh_tasks, return_exceptions=True)
    
    db.expire_all()
    case = db.query(RevenueRiskCase).get(case_id)
    print(f"Resulting amount recovered: {case.amount_recovered}")
    
    # Assert ONE logical recovery amount
    assert case.amount_recovered == 10000, f"Expected 10000 recovered, got {case.amount_recovered}"
    assert case.status == CaseStatus.RECOVERED
    
    print("\nConcurrency test PASSED. Evidence captured.")
    
    from app.models.domain import CaseDecision, AuditEvent, WebhookEvent
    db.query(CaseAction).filter_by(case_id=case_id).delete()
    db.query(CaseDecision).filter_by(case_id=case_id).delete()
    db.query(AuditEvent).filter_by(case_id=case_id).delete()
    db.query(WebhookEvent).filter_by(event_id=payload["id"]).delete()
    db.query(RevenueRiskCase).filter_by(id=case_id).delete()
    db.commit()
    db.close()
