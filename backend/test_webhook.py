import sys
import os
import hmac
import hashlib
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database.core import SessionLocal
from app.models.domain import RevenueRiskCase, CaseStatus, CaseAction, AuditEvent
from app.agent.agent import RevPilotAgent
from app.razorpay.webhooks import WebhookVerifier

def test_webhook_flow():
    db = SessionLocal()
    verifier = WebhookVerifier()
    
    # Simulate an incoming webhook payload
    payload = {
        "entity": "event",
        "account_id": "acc_BFQ7uQEaa7j2z7",
        "event": "payment_link.paid",
        "contains": ["payment_link"],
        "payload": {
            "payment_link": {
                "entity": {
                    "id": "plink_test123",
                    "reference_id": "case_case_agent_test_pos_action_RETRY_PAYMENT_OPPORTUNITY_attempt_0",
                    "status": "paid",
                    "amount_paid": 2000000
                }
            }
        },
        "created_at": 1691735748
    }
    raw_body = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    signature = hmac.new(verifier.secret, msg=raw_body, digestmod=hashlib.sha256).hexdigest()
    
    # 1. Verify signature
    is_valid = verifier.verify_signature(raw_body, signature)
    print(f"Webhook Signature Valid: {is_valid}")
    if not is_valid:
        return

    # 2. Process webhook event
    print(f"Processing event: {payload['event']}")
    if payload['event'] == 'payment_link.paid':
        ref_id = payload['payload']['payment_link']['entity']['reference_id']
        amount_paid = payload['payload']['payment_link']['entity']['amount_paid']
        
        # We encoded the case_id inside the reference_id (or we can look it up by idempotency_key)
        # reference_id matches our idempotency_key exactly!
        action = db.query(CaseAction).filter_by(idempotency_key=ref_id).first()
        if action:
            case_id = action.case_id
            print(f"Found matching case: {case_id}")
            
            # Update action status
            action.status = "SUCCESS"
            
            # Update case status
            case = db.query(RevenueRiskCase).filter_by(id=case_id).first()
            if case:
                case.status = CaseStatus.RECOVERED
                print(f"Case {case_id} marked as RECOVERED. Recovered Amount: {amount_paid}")
                
                # Record Audit
                db.add(AuditEvent(
                    case_id=case_id,
                    event_type="WEBHOOK_RECEIVED",
                    description=f"Received payment_link.paid for {amount_paid} paise",
                    metadata_blob={"raw": payload}
                ))
            db.commit()

if __name__ == "__main__":
    test_webhook_flow()
