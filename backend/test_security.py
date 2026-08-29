import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database.core import SessionLocal
from app.models.domain import RevenueRiskCase, CaseStatus, CaseAction
from sqlalchemy.exc import IntegrityError, DataError
import hmac
import hashlib
import json
import uuid

@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()

# ---------------------------------------------------------
# 1. DATABASE SAFETY (Negative Amounts & Oversized Inputs)
# ---------------------------------------------------------
def test_db_rejects_negative_amount(db):
    case = RevenueRiskCase(
        id=str(uuid.uuid4()),
        customer_id="cust_1",
        case_type="FAILED_PAYMENT",
        amount_at_risk=-500, # NEGATIVE!
        status=CaseStatus.OPEN
    )
    db.add(case)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

def test_db_rejects_oversized_string(db):
    huge_string = "A" * 20000
    case = RevenueRiskCase(
        id=str(uuid.uuid4()),
        customer_id=huge_string, # Should fail if varchar limits exist
        case_type="FAILED_PAYMENT",
        amount_at_risk=1000,
        status=CaseStatus.OPEN
    )
    db.add(case)
    with pytest.raises((IntegrityError, DataError)): # PostgreSQL raises DataError for String truncation
        db.commit()
    db.rollback()

# ---------------------------------------------------------
# 2. STATE MACHINE FUZZING
# ---------------------------------------------------------
def test_invalid_state_transition(db):
    case = RevenueRiskCase(
        id=str(uuid.uuid4()), customer_id="c1", case_type="FAILED_PAYMENT", amount_at_risk=100, status=CaseStatus.STOPPED
    )
    db.add(case)
    db.commit()
    
    # Attempt illegal transition
    with pytest.raises(ValueError, match="Invalid state transition"):
        case.transition_to(CaseStatus.EXECUTING)

# ---------------------------------------------------------
# 3. PAGINATION & RESOURCE ABUSE
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_pagination_limits(db):
    from app.api.auth import create_access_token
    from app.models.user import User, UserRole
    # Provide an admin user
    try:
        user = User(id="sec_admin", username="sec_admin", hashed_password="pwd", role=UserRole.ADMIN)
        db.add(user)
        db.commit()
    except:
        db.rollback()
    token = create_access_token({"sub": "sec_admin"})
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {token}"}
        
        # Request huge page size
        response = await ac.get("/api/cases?limit=1000000", headers=headers)
        assert response.status_code == 422 # Validation Error from Pydantic

# ---------------------------------------------------------
# 4. AUTHENTICATION & RBAC
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_unauthorized_access_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/cases")
        assert response.status_code in [401, 403]

# ---------------------------------------------------------
# 5. WEBHOOK CONCURRENCY (DOUBLE COUNTING)
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_concurrent_webhooks(db):
    import os
    # Setup case and action
    case_id = str(uuid.uuid4())
    idem_key = str(uuid.uuid4())
    event_id = str(uuid.uuid4())
    case = RevenueRiskCase(id=case_id, customer_id="c1", case_type="FAILED_PAYMENT", amount_at_risk=100, status=CaseStatus.WAITING_FOR_OUTCOME)
    action = CaseAction(id=str(uuid.uuid4()), case_id=case_id, action_type="CREATE_PAYMENT_LINK", status="PENDING", idempotency_key=idem_key)
    db.add(case)
    db.add(action)
    db.commit()

    # Create payload
    payload = {
        "event": "payment_link.paid",
        "payload": {
            "payment_link": {
                "entity": {
                    "reference_id": idem_key,
                    "amount_paid": 100
                }
            }
        }
    }
    raw_body = json.dumps(payload).encode()
    secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "mock_webhook_secret").encode('utf-8')
    signature = hmac.new(secret, msg=raw_body, digestmod=hashlib.sha256).hexdigest()
    headers = {"X-Razorpay-Signature": signature, "X-Razorpay-Event-Id": event_id}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Fire 5 webhooks concurrently
        tasks = [ac.post("/api/webhook/razorpay", content=raw_body, headers=headers) for _ in range(5)]
        responses = await asyncio.gather(*tasks)

        # All should return 200/202, but only ONE processed it (the others hit the duplicate event catch)
        successes = [r for r in responses if r.status_code in [200, 202]]
        assert len(successes) == 5 

    # Verify DB: Should only be ONE recovery audit event and amount recovered should be EXACTLY 100
    db.refresh(case)
    assert case.amount_recovered == 100
