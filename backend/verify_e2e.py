import json
from app.database.core import SessionLocal
from app.models.domain import RevenueRiskCase, WebhookEvent, AuditEvent

def check():
    db = SessionLocal()
    case_id = "8beee88e-eee3-4a70-abb6-2064199b8c9e"
    
    case = db.query(RevenueRiskCase).get(case_id)
    if not case:
        print("Case not found!")
        return
        
    print(f"CASE STATUS: {case.status}")
    print(f"AMOUNT AT RISK: {case.amount_at_risk}")
    print(f"AMOUNT RECOVERED: {case.amount_recovered}")
    
    # Check Webhooks
    print("\nWEBHOOK EVENTS RECEIVED:")
    whs = db.query(WebhookEvent).all()
    for wh in whs:
        print(f" - {wh.event_type} | ID: {wh.event_id} | Created: {wh.created_at}")
        
    # Check Audits
    print("\nAUDIT TRAIL:")
    audits = db.query(AuditEvent).filter_by(case_id=case_id).order_by(AuditEvent.created_at).all()
    for a in audits:
        print(f" - {a.event_type}: {a.description}")
        if a.event_type == "WEBHOOK_RECEIVED":
            print(f"   Payload: {json.dumps(a.metadata_blob)[:200]}...")
            
    db.close()

if __name__ == "__main__":
    check()
