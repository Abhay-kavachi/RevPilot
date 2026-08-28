from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any
import json
from app.database.core import get_db
from app.models.domain import RevenueRiskCase, CaseAction, CaseDecision, AuditEvent, CaseStatus
from app.agent.agent import RevPilotAgent
from app.razorpay.webhooks import WebhookVerifier

router = APIRouter()

@router.get("/cases")
def list_cases(db: Session = Depends(get_db)):
    cases = db.query(RevenueRiskCase).order_by(RevenueRiskCase.created_at.desc()).all()
    return cases

@router.get("/cases/{case_id}")
def get_case(case_id: str, db: Session = Depends(get_db)):
    case = db.query(RevenueRiskCase).filter(RevenueRiskCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case

@router.get("/cases/{case_id}/audit")
def get_case_audit(case_id: str, db: Session = Depends(get_db)):
    return db.query(AuditEvent).filter(AuditEvent.case_id == case_id).order_by(AuditEvent.created_at.desc()).all()

@router.get("/cases/{case_id}/decisions")
def get_case_decisions(case_id: str, db: Session = Depends(get_db)):
    return db.query(CaseDecision).filter(CaseDecision.case_id == case_id).order_by(CaseDecision.created_at.desc()).all()

@router.get("/dashboard/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    total_cases = db.query(func.count(RevenueRiskCase.id)).scalar()
    recovered_cases = db.query(func.count(RevenueRiskCase.id)).filter(RevenueRiskCase.status == CaseStatus.RECOVERED).scalar()
    
    total_at_risk = db.query(func.sum(RevenueRiskCase.amount_at_risk)).scalar() or 0
    total_recovered = db.query(func.sum(RevenueRiskCase.amount_at_risk)).filter(RevenueRiskCase.status == CaseStatus.RECOVERED).scalar() or 0
    
    return {
        "total_cases": total_cases,
        "recovered_cases": recovered_cases,
        "total_at_risk": total_at_risk,
        "total_recovered": total_recovered,
        "recovery_rate": (recovered_cases / total_cases * 100) if total_cases > 0 else 0
    }

@router.post("/webhook/razorpay")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    
    verifier = WebhookVerifier()
    if not verifier.verify_signature(raw_body, signature):
        raise HTTPException(status_code=400, detail="Invalid signature")
        
    payload = json.loads(raw_body)
    event_type = payload.get("event")
    
    # Process event
    if event_type == 'payment_link.paid':
        ref_id = payload.get("payload", {}).get("payment_link", {}).get("entity", {}).get("reference_id")
        amount_paid = payload.get("payload", {}).get("payment_link", {}).get("entity", {}).get("amount_paid")
        
        if ref_id:
            action = db.query(CaseAction).filter_by(idempotency_key=ref_id).first()
            if action:
                case_id = action.case_id
                action.status = "SUCCESS"
                case = db.query(RevenueRiskCase).filter_by(id=case_id).first()
                if case:
                    case.status = CaseStatus.RECOVERED
                    db.add(AuditEvent(
                        case_id=case_id,
                        event_type="WEBHOOK_RECEIVED",
                        description=f"Received payment_link.paid for {amount_paid} paise",
                        metadata_blob={"raw": payload}
                    ))
                db.commit()
    return {"status": "ok"}
