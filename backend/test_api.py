from fastapi.testclient import TestClient
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from app.database.core import SessionLocal
from app.models.domain import RevenueRiskCase, CaseStatus

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_endpoints():
    db = SessionLocal()
    try:
        # Check cases
        response = client.get("/api/cases")
        assert response.status_code == 200
        cases = response.json()
        print(f"Loaded {len(cases)} cases for Queue.")
        
        if cases:
            case_id = cases[0]["id"]
            
            # Check case detail
            r = client.get(f"/api/cases/{case_id}")
            assert r.status_code == 200
            print(f"Loaded case detail for {case_id}")
            
            # Check audit
            r = client.get(f"/api/cases/{case_id}/audit")
            assert r.status_code == 200
            print(f"Loaded {len(r.json())} audit events for Audit Timeline.")
            
            # Check decisions
            r = client.get(f"/api/cases/{case_id}/decisions")
            assert r.status_code == 200
            print(f"Loaded {len(r.json())} decisions for Decision Trace.")
            
        # Check Dashboard
        response = client.get("/api/dashboard/stats")
        assert response.status_code == 200
        print("Loaded Dashboard stats:", response.json())
        
    finally:
        db.close()

if __name__ == "__main__":
    test_health()
    test_endpoints()
    print("All endpoints tested successfully for Milestone 7 data requirements!")
