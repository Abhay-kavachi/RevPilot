import json
from app.database.core import SessionLocal
from app.models.domain import RevenueRiskCase, WebhookEvent, AuditEvent

def check():
    db = SessionLocal()
    case_id = "91f9382f-b969-40ad-b7d1-556f482cc8a0"
    
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
            print(f"   Payload: {json.dumps(a.metadata_blob, indent=2)}")
            
    db.close()

if __name__ == "__main__":
    check()
