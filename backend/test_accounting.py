import pytest
import asyncio
import uuid
import json
from sqlalchemy.orm import Session
from app.database.core import SessionLocal
from app.models.domain import RevenueRiskCase, CaseStatus, CaseAction, WebhookEvent, AuditEvent
from app.api.endpoints import razorpay_webhook
from fastapi import Request, HTTPException
from httpx import Headers
from unittest.mock import patch

class MockRequest(Request):
    def __init__(self, body_bytes: bytes, headers: dict):
        scope = {
            "type": "http",
            "headers": [(k.lower().encode(), str(v).encode()) for k, v in headers.items()]
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

def setup_case(db: Session, amount_at_risk: int = 10000):
    case_id = str(uuid.uuid4())
    case = RevenueRiskCase(
        id=case_id,
        amount_at_risk=amount_at_risk,
        amount_recovered=0,
        case_type="FAILED_PAYMENT",
        status=CaseStatus.WAITING_FOR_OUTCOME
    )
    db.add(case)
    
    action = CaseAction(
        id=str(uuid.uuid4()),
        case_id=case_id,
        action_type="CREATE_PAYMENT_LINK",
        idempotency_key=f"test_idem_{case_id}",
        status="PENDING"
    )
    db.add(action)
    db.commit()
    return case_id, action.idempotency_key

async def fire_webhook(db: Session, event_id: str, event_type: str, ref_id: str, payment_amount: int, omit_event_id: bool = False, omit_amount: bool = False, invalid_amount: bool = False):
    payload = {
        "event": event_type,
        "id": event_id if event_id else f"evt_{uuid.uuid4()}",
        "payload": {
            "payment_link": {
                "entity": {
                    "reference_id": ref_id
                }
            },
            "payment": {
                "entity": {}
            }
        }
    }
    
    if not omit_amount:
        if invalid_amount:
            payload["payload"]["payment"]["entity"]["amount"] = "not_an_int"
        else:
            payload["payload"]["payment"]["entity"]["amount"] = payment_amount
            
    if omit_event_id:
        # omit from payload and headers
        payload.pop("id", None)
        headers = {"x-razorpay-signature": "mock_sig"}
    else:
        headers = {"x-razorpay-signature": "mock_sig", "x-razorpay-event-id": event_id}
        
    body_bytes = json.dumps(payload).encode()
    
    with patch("app.api.endpoints.WebhookVerifier.verify_signature", return_value=True):
        req = MockRequest(body_bytes, headers)
        try:
            return await razorpay_webhook(req, db)
        except HTTPException as e:
            return e

@pytest.mark.asyncio
async def test_partial_payment_semantics(db: Session):
    case_id, ref_id = setup_case(db, 10000)
    
    # 1. First Partial Payment
    evt1 = f"evt_{uuid.uuid4()}"
    res = await fire_webhook(db, evt1, "payment_link.partially_paid", ref_id, 4000)
    assert isinstance(res, dict) and res["status"] == "ok"
    
    db.expire_all()
    case = db.query(RevenueRiskCase).get(case_id)
    assert case.amount_recovered == 4000
    assert case.status == CaseStatus.WAITING_FOR_OUTCOME, "Should NOT transition to RECOVERED yet"
    
    # 2. Duplicate First Partial Payment (Replay Attack)
    res = await fire_webhook(db, evt1, "payment_link.partially_paid", ref_id, 4000)
    assert isinstance(res, dict) and res["message"] == "duplicate event"
    db.expire_all()
    case = db.query(RevenueRiskCase).get(case_id)
    assert case.amount_recovered == 4000, "Cumulative amount must not double-count duplicate events"
    
    # 3. Second Partial Payment (Completing the total)
    evt2 = f"evt_{uuid.uuid4()}"
    res = await fire_webhook(db, evt2, "payment_link.paid", ref_id, 6000)
    assert isinstance(res, dict) and res["status"] == "ok"
    
    db.expire_all()
    case = db.query(RevenueRiskCase).get(case_id)
    assert case.amount_recovered == 10000
    assert case.status == CaseStatus.RECOVERED, "Should transition to RECOVERED upon full payment"

@pytest.mark.asyncio
async def test_overpayment_ceiling(db: Session):
    case_id, ref_id = setup_case(db, 5000)
    
    # Overpayment
    evt1 = f"evt_{uuid.uuid4()}"
    await fire_webhook(db, evt1, "payment_link.paid", ref_id, 10000)
    
    db.expire_all()
    case = db.query(RevenueRiskCase).get(case_id)
    assert case.amount_recovered == 5000, "Should cap recovery at amount_at_risk"
    assert case.status == CaseStatus.RECOVERED
    
@pytest.mark.asyncio
async def test_missing_event_id_rejection(db: Session):
    case_id, ref_id = setup_case(db, 5000)
    
    # Missing Event ID entirely
    res = await fire_webhook(db, "", "payment_link.paid", ref_id, 5000, omit_event_id=True)
    assert isinstance(res, HTTPException)
    assert res.status_code == 400
    assert "Missing Event ID" in res.detail
    
@pytest.mark.asyncio
async def test_payload_validation(db: Session):
    case_id, ref_id = setup_case(db, 5000)
    
    # Missing reference_id
    res = await fire_webhook(db, f"evt_{uuid.uuid4()}", "payment_link.paid", None, 5000)
    assert isinstance(res, HTTPException)
    assert res.status_code == 400
    assert "Missing reference_id" in res.detail
    
    # Missing amount
    res = await fire_webhook(db, f"evt_{uuid.uuid4()}", "payment_link.paid", ref_id, 5000, omit_amount=True)
    assert isinstance(res, HTTPException)
    assert res.status_code == 400
    assert "Invalid or missing payment amount" in res.detail
    
    # Invalid amount (string)
    res = await fire_webhook(db, f"evt_{uuid.uuid4()}", "payment_link.paid", ref_id, 5000, invalid_amount=True)
    assert isinstance(res, HTTPException)
    assert res.status_code == 400
    assert "Invalid or missing payment amount" in res.detail

    # Negative amount
    res = await fire_webhook(db, f"evt_{uuid.uuid4()}", "payment_link.paid", ref_id, -100)
    assert isinstance(res, HTTPException)
    assert res.status_code == 400
    assert "Invalid or missing payment amount" in res.detail
