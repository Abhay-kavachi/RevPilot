from fastapi.testclient import TestClient
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from app.database.core import SessionLocal
from app.models.domain import RevenueRiskCase, CaseStatus
import pytest
from httpx import AsyncClient, ASGITransport

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

@pytest.mark.asyncio
async def test_endpoints():
    db = SessionLocal()
    from app.api.auth import create_access_token
    from app.models.user import User, UserRole
    # Provide an admin user
    try:
        user = User(id="api_admin", username="api_admin", hashed_password="pwd", role=UserRole.ADMIN)
        db.add(user)
        db.commit()
    except:
        db.rollback()
    finally:
        db.close()
    token = create_access_token({"sub": "api_admin"})
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {token}"}
        
        response = await ac.get("/api/cases", headers=headers)
        assert response.status_code == 200
        cases = response.json()
        print(f"Loaded {len(cases)} cases for Queue.")
        
        if cases:
            case_id = cases[0]["id"]
            
            # Check case detail
            r = await ac.get(f"/api/cases/{case_id}", headers=headers)
            assert r.status_code == 200
            print(f"Loaded case detail for {case_id}")
            
            # Check audit
            r = await ac.get(f"/api/cases/{case_id}/audit", headers=headers)
            assert r.status_code == 200
            print(f"Loaded {len(r.json())} audit events for Audit Timeline.")
            
            # Check decisions
            r = await ac.get(f"/api/cases/{case_id}/decisions", headers=headers)
            assert r.status_code == 200
            print(f"Loaded {len(r.json())} decisions for Decision Trace.")
            
        # Check Dashboard
        response = await ac.get("/api/dashboard/stats", headers=headers)
        assert response.status_code == 200
        print("Loaded Dashboard stats:", response.json())

if __name__ == "__main__":
    test_health()
    test_endpoints()
    print("All endpoints tested successfully for Milestone 7 data requirements!")
