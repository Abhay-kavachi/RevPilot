import pytest
import asyncio
import json
import uuid
from sqlalchemy.orm import Session
from app.database.core import SessionLocal
from app.models.domain import RevenueRiskCase, CaseStatus, CaseAction, WebhookEvent
from app.api.endpoints import razorpay_webhook
from fastapi import Request, HTTPException
import hmac
import hashlib
from unittest.mock import patch
from app.core.config import settings

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

@pytest.fixture
def db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()

def sign_payload(payload_dict):
    body_bytes = json.dumps(payload_dict, separators=(',', ':')).encode('utf-8')
    secret = settings.razorpay.WEBHOOK_SECRET.encode()
    expected_sig = hmac.new(secret, body_bytes, hashlib.sha256).hexdigest()
    return body_bytes, expected_sig

def test_webhook_invalid_signature(db: Session):
    payload = {"event": "payment_link.paid", "id": f"evt_{uuid.uuid4()}"}
    body_bytes, _ = sign_payload(payload)
    
    req = MockRequest(body_bytes, {
        "x-razorpay-signature": "wrong_signature",
        "x-razorpay-event-id": payload["id"]
    })
    
    with pytest.raises(HTTPException) as exc:
        asyncio.run(razorpay_webhook(req, db))
    
    assert exc.value.status_code == 400
    assert "Invalid signature" in exc.value.detail

def test_webhook_deduplication(db: Session):
    case_id = str(uuid.uuid4())
    case = RevenueRiskCase(id=case_id, amount_at_risk=5000, amount_recovered=0, case_type="F", status=CaseStatus.WAITING_FOR_OUTCOME)
    db.add(case)
    action = CaseAction(id=str(uuid.uuid4()), case_id=case_id, action_type="CREATE_PAYMENT_LINK", idempotency_key=f"idem_{case_id}")
    db.add(action)
    db.commit()
    
    payload = {
        "event": "payment_link.paid",
        "id": f"evt_{uuid.uuid4()}",
        "payload": {
            "payment_link": {"entity": {"reference_id": action.idempotency_key}},
            "payment": {"entity": {"amount": 5000}}
        }
    }
    body_bytes, expected_sig = sign_payload(payload)
    
    req = MockRequest(body_bytes, {
        "x-razorpay-signature": expected_sig,
        "x-razorpay-event-id": payload["id"]
    })
    
    # First delivery
    res = asyncio.run(razorpay_webhook(req, db))
    assert res == {"status": "ok"}
    db.refresh(case)
    assert case.amount_recovered == 5000
    
    # Second delivery
    res = asyncio.run(razorpay_webhook(req, db))
    assert res == {"status": "ok", "message": "duplicate event"}
    db.refresh(case)
    assert case.amount_recovered == 5000 # No double counting

def test_webhook_missing_event_id_handled_safely(db: Session):
    # If no ID is provided, it should safely reject with 400 instead of crashing or sharing "unknown_event"
    payload = {"event": "payment_link.paid"}
    body_bytes, expected_sig = sign_payload(payload)
    
    req = MockRequest(body_bytes, {
        "x-razorpay-signature": expected_sig
        # Missing x-razorpay-event-id
    })
    
    with pytest.raises(HTTPException) as exc:
        asyncio.run(razorpay_webhook(req, db))
    
    assert exc.value.status_code == 400
    assert "Missing Event ID" in exc.value.detail
