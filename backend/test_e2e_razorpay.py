import pytest
import os
import uuid
import asyncio
from sqlalchemy.orm import Session
from app.database.core import SessionLocal
from app.models.domain import RevenueRiskCase, CaseStatus, CaseAction
from app.agent.agent import RevPilotAgent
from app.api.endpoints import razorpay_webhook
import json
from unittest.mock import patch

from fastapi import Request

class MockRequest(Request):
    def __init__(self, body_bytes: bytes, headers: dict):
        scope = {
            "type": "http",
            "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()]
        }
        super().__init__(scope)
        self._body_bytes = body_bytes
        
    async def body(self) -> bytes:
        return self._body_bytes

def test_real_razorpay_e2e():
    # Only run if we are fully configured with real keys
    from app.core.config import settings
    if "mock" in settings.razorpay.KEY_ID or settings.razorpay.KEY_ID == "":
        pytest.skip("Real Razorpay credentials not found, skipping E2E test.")
        
    db = SessionLocal()
    case_id = str(uuid.uuid4())
    try:
        # 1. Create a RevenueRiskCase
        case = RevenueRiskCase(
            id=case_id,
            amount_at_risk=5000, # 50 INR
            amount_recovered=0,
            case_type="FAILED_PAYMENT",
            status=CaseStatus.OPEN
        )
        db.add(case)
        db.commit()
        
        # 2. Run the RevPilot Agent Processing
        agent = RevPilotAgent(db)
        agent.process(case_id)
        
        # 3. Verify Razorpay Action Creation
        db.refresh(case)
        assert case.status == CaseStatus.WAITING_FOR_OUTCOME
        
        action = db.query(CaseAction).filter(CaseAction.case_id == case_id).first()
        assert action is not None
        assert action.action_type in ["CREATE_PAYMENT_LINK", "RETRY_PAYMENT_OPPORTUNITY"]
        assert action.provider_reference_id is not None
        assert action.provider_reference_id.startswith("plink_") or action.provider_reference_id != ""
        
        provider_ref = action.provider_reference_id
        
        print(f"\nE2E Evidence - Provider Reference ID: {provider_ref}")
        
        # 4. Simulate the Webhook arriving from Razorpay for this exact link
        # We don't have to manually pay the link in the test (which requires browser automation)
        # We can construct the webhook that Razorpay WOULD send upon payment.
        
        payload = {
            "event": "payment_link.paid",
            "id": f"evt_{uuid.uuid4()}",
            "payload": {
                "payment_link": {
                    "entity": {
                        "id": provider_ref,
                        "reference_id": action.idempotency_key,
                        "amount": 5000,
                        "amount_paid": 5000,
                        "status": "paid"
                    }
                },
                "payment": {
                    "entity": {
                        "amount": 5000
                    }
                }
            },
            "created_at": 1600000000
        }
        
        import hmac
        import hashlib
        # Generate valid signature
        body_bytes = json.dumps(payload, separators=(',', ':')).encode()
        secret = settings.razorpay.WEBHOOK_SECRET.encode()
        expected_sig = hmac.new(secret, body_bytes, hashlib.sha256).hexdigest()
        
        req = MockRequest(body_bytes, {
            "x-razorpay-signature": expected_sig,
            "x-razorpay-event-id": payload["id"]
        })
        
        asyncio.run(razorpay_webhook(req, db))
        
        # 5. Verify Final State
        db.refresh(case)
        db.refresh(action)
        
        assert case.status == CaseStatus.RECOVERED
        assert case.amount_recovered == 5000
        assert action.status == "SUCCESS"
        
        print(f"E2E Evidence - Final Case Status: {case.status}")
        print(f"E2E Evidence - Recovered Amount: {case.amount_recovered}")
        
    finally:
        # Cleanup
        from app.models.domain import AuditEvent, CaseDecision
        db.query(CaseAction).filter(CaseAction.case_id == case_id).delete()
        db.query(AuditEvent).filter(AuditEvent.case_id == case_id).delete()
        db.query(CaseDecision).filter(CaseDecision.case_id == case_id).delete()
        db.query(RevenueRiskCase).filter(RevenueRiskCase.id == case_id).delete()
        db.commit()
        db.close()
