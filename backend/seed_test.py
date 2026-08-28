import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database.core import SessionLocal
from app.models.domain import RevenueRiskCase, CaseStatus

def seed_data():
    db = SessionLocal()
    try:
        # Create a test case
        case = RevenueRiskCase(
            id="case_failed_pmt_001",
            amount_at_risk=1500000, # 15000 INR
            currency="INR",
            case_type="FAILED_PAYMENT",
            status=CaseStatus.OPEN,
            customer_id="cust_test_1",
            customer_email="test@example.com",
            customer_phone="9999999999",
            attempt_count=0,
            max_attempts=3
        )
        db.add(case)
        db.commit()
        db.refresh(case)
        print(f"Successfully seeded case: {case.id} with status {case.status} and amount {case.amount_at_risk}")
    except Exception as e:
        print(f"Error seeding data: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
