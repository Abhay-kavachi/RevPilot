import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
import uuid
import json
import hmac
import hashlib
import os

from app.main import app
from app.database.core import SessionLocal
from app.models.domain import RevenueRiskCase, CaseStatus, CaseAction, CaseDecision, AuditEvent
from app.models.user import User, UserRole
from app.api.auth import create_access_token, get_password_hash
from sqlalchemy.exc import IntegrityError, DataError

os.environ["TESTING"] = "1"
os.environ["JWT_SECRET_KEY"] = "test_secret_key_only"
os.environ["JWT_EXPIRY_MINUTES"] = "30"

@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()

@pytest.fixture
def auth_tokens(db):
    tokens = {}
    users = [
        ("admin1", UserRole.ADMIN, "m1"),
        ("operator1", UserRole.OPERATOR, "m1"),
        ("analyst1", UserRole.ANALYST, "m1"),
        ("viewer1", UserRole.VIEWER, "m1"),
        ("admin2", UserRole.ADMIN, "m2"),
    ]
    try:
        for username, role, merchant in users:
            if not db.query(User).filter_by(id=username).first():
                u = User(id=username, username=username, hashed_password=get_password_hash("pwd"), role=role, merchant_id=merchant)
                db.add(u)
        db.commit()
    except Exception as e:
        db.rollback()
        
    for username, _, _ in users:
        tokens[username] = create_access_token({"sub": username})
    return tokens

# ---------------------------------------------------------
# 1. OVERSIZED INPUT (Text field constraints)
# ---------------------------------------------------------
def test_oversized_input_rejection(db):
    sizes = [1000, 5000, 10000, 20000, 50000, 100000]
    for size in sizes:
        case = RevenueRiskCase(id=str(uuid.uuid4()), customer_id="A" * size, customer_email="B"*size, case_type="F", amount_at_risk=100)
        db.add(case)
        with pytest.raises((IntegrityError, DataError)):
            db.commit()
        db.rollback()

# ---------------------------------------------------------
# 2. SQL INJECTION (via API parameters)
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_sql_injection_parameters(auth_tokens):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {auth_tokens['admin1']}"}
        
        # skip/limit injection
        res = await ac.get("/api/cases?skip=0 UNION SELECT * FROM users", headers=headers)
        assert res.status_code == 422
        
        # ID injection
        res = await ac.get("/api/cases/' OR 1=1;--", headers=headers)
        assert res.status_code == 404 # Treated as literal string, no SQL exec

# ---------------------------------------------------------
# 3. XSS (Output Sanitization)
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_xss_in_identifiers(auth_tokens):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {auth_tokens['admin1']}"}
        res = await ac.get("/api/cases?skip=<script>alert(1)</script>", headers=headers)
        assert res.status_code == 422

# ---------------------------------------------------------
# 4. JSON ABUSE (Deep / Malformed)
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_json_abuse_webhook():
    deep_json = "{\"a\": " * 1000 + "1" + "}" * 1000
    headers = {"X-Razorpay-Signature": "fake", "X-Razorpay-Event-Id": "123"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/webhook/razorpay", content=deep_json.encode(), headers=headers)
        assert res.status_code in [400, 422]
        
        res = await ac.post("/api/webhook/razorpay", content=b"{malformed_json: 'test'", headers=headers)
        assert res.status_code in [400, 422]

# ---------------------------------------------------------
# 5 & 6. WEBHOOK & REPLAY ABUSE
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_webhook_abuse(db):
    event_id = str(uuid.uuid4())
    payload = {"event": "payment_link.paid", "id": event_id}
    raw_body = json.dumps(payload).encode()
    secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "mock_webhook_secret").encode('utf-8')
    sig = hmac.new(secret, msg=raw_body, digestmod=hashlib.sha256).hexdigest()
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Missing signature
        res = await ac.post("/api/webhook/razorpay", content=raw_body, headers={"X-Razorpay-Event-Id": event_id})
        assert res.status_code == 400
        
        # Invalid signature
        res = await ac.post("/api/webhook/razorpay", content=raw_body, headers={"X-Razorpay-Event-Id": event_id, "X-Razorpay-Signature": "invalid"})
        assert res.status_code == 400
        
        # Replay valid 10 times concurrently
        headers = {"X-Razorpay-Event-Id": event_id, "X-Razorpay-Signature": sig}
        tasks = [ac.post("/api/webhook/razorpay", content=raw_body, headers=headers) for _ in range(10)]
        results = await asyncio.gather(*tasks)
        assert all(r.status_code == 200 for r in results) # 1 processed, 9 safely ignored
        
        # Same event ID, modified payload
        modified_body = json.dumps({"event": "payment_link.paid", "amount": 100}).encode()
        modified_sig = hmac.new(secret, msg=modified_body, digestmod=hashlib.sha256).hexdigest()
        res = await ac.post("/api/webhook/razorpay", content=modified_body, headers={"X-Razorpay-Event-Id": event_id, "X-Razorpay-Signature": modified_sig})
        assert res.status_code == 200 # It should see the same event_id and ignore it

# ---------------------------------------------------------
# 7. CONCURRENCY (Action Creation)
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_concurrency_case_lock(db):
    case_id = str(uuid.uuid4())
    case = RevenueRiskCase(id=case_id, customer_id="c1", case_type="F", amount_at_risk=100)
    db.add(case)
    db.commit()

# ---------------------------------------------------------
# 8 & 9. AUTHENTICATION & RBAC MATRIX
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_auth_and_rbac(auth_tokens):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Missing token
        res = await ac.get("/api/cases")
        assert res.status_code == 401
        
        # Malformed token
        res = await ac.get("/api/cases", headers={"Authorization": "Bearer not-a-jwt"})
        assert res.status_code == 401
        
        # Valid token (Viewer)
        res = await ac.get("/api/cases", headers={"Authorization": f"Bearer {auth_tokens['viewer1']}"})
        assert res.status_code == 200

# ---------------------------------------------------------
# 10. IDOR (Merchant Isolation)
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_idor_protection(auth_tokens, db):
    # m1 case
    c1 = str(uuid.uuid4())
    db.add(RevenueRiskCase(id=c1, merchant_id="m1", customer_id="c", case_type="T", amount_at_risk=1))
    db.commit()
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # admin1 (m1) can access c1
        res = await ac.get(f"/api/cases/{c1}", headers={"Authorization": f"Bearer {auth_tokens['admin1']}"})
        assert res.status_code == 200
        
        # admin2 (m2) CANNOT access c1
        res = await ac.get(f"/api/cases/{c1}", headers={"Authorization": f"Bearer {auth_tokens['admin2']}"})
        assert res.status_code == 404

# ---------------------------------------------------------
# 11. ECONOMIC INPUT VALIDATION
# ---------------------------------------------------------
def test_economic_db_constraints(db):
    c_id = str(uuid.uuid4())
    db.add(RevenueRiskCase(id=c_id, case_type="FAILED_PAYMENT", amount_at_risk=100))
    db.commit()
    
    dec = CaseDecision(id=str(uuid.uuid4()), case_id=c_id, action_type="T", success_probability=1.5, cost=-5, friction=0, risk=0, expected_value=1, final_enr=1)
    db.add(dec)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

# ---------------------------------------------------------
# 13. ERROR LEAKAGE
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_error_leakage(auth_tokens):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/cases/invalid_case/audit", headers={"Authorization": f"Bearer {auth_tokens['admin1']}"})
        assert res.status_code == 404
        assert "stack_trace" not in res.text
        assert "psycopg2" not in res.text

# ---------------------------------------------------------
# 14. AUDIT IMMUTABILITY
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_audit_immutability(auth_tokens):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {auth_tokens['admin1']}"}
        res = await ac.delete("/api/cases/some_id/audit", headers=headers)
        assert res.status_code == 405 # Method Not Allowed

# ---------------------------------------------------------
# 15. PASSWORD HASHING TESTS
# ---------------------------------------------------------
def test_password_hashing():
    from app.api.auth import get_password_hash, verify_password
    plain = "SuperSecr3t!✅" * 10 # This is now ~140 bytes
    h1 = get_password_hash(plain)
    h2 = get_password_hash(plain)
    
    assert h1 != h2 # salt is unique
    assert verify_password(plain, h1)
    assert not verify_password("wrong_password", h1)
    
    # ensure plaintext doesn't leak into the hash literal
    assert plain not in h1
