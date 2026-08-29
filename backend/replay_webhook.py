import httpx
from app.database.core import SessionLocal
from app.models.domain import WebhookEvent

def replay():
    db = SessionLocal()
    # Find the partially_paid event
    wh = db.query(WebhookEvent).filter_by(event_type="payment_link.partially_paid").order_by(WebhookEvent.created_at.desc()).first()
    if not wh:
        print("No partially_paid event found.")
        return
        
    print(f"Found event: {wh.event_id}")
    payload = wh.payload
    
    # Delete the deduplication record so we can replay it
    db.delete(wh)
    db.commit()
    print("Deleted deduplication record.")
    
    # Sign it and post it
    import hmac
    import hashlib
    import json
    from app.core.config import settings
    
    body_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    secret = settings.razorpay.WEBHOOK_SECRET.encode()
    expected_sig = hmac.new(secret, body_bytes, hashlib.sha256).hexdigest()
    
    print("Posting to localhost...")
    resp = httpx.post(
        "http://localhost:8000/webhook/razorpay",
        content=body_bytes,
        headers={
            "X-Razorpay-Signature": expected_sig,
            "X-Razorpay-Event-Id": wh.event_id,
            "Content-Type": "application/json"
        }
    )
    print(resp.status_code, resp.text)
    
if __name__ == "__main__":
    replay()
