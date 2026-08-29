from fastapi import APIRouter, Depends, Request, HTTPException, Header, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from typing import List, Dict, Any
import json
import os
from app.database.core import get_db
from app.models.domain import RevenueRiskCase, CaseAction, CaseDecision, AuditEvent, CaseStatus, WebhookEvent
from app.models.user import User, UserRole
from app.api.auth import verify_password, create_access_token, require_role, get_current_user
from app.agent.agent import RevPilotAgent
from app.razorpay.webhooks import WebhookVerifier

router = APIRouter()

@router.post("/auth/token")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer", "role": user.role}


# All read operations allow VIEWER and above
READ_ROLES = [UserRole.ADMIN, UserRole.OPERATOR, UserRole.ANALYST, UserRole.VIEWER]
# Manual actions would require OPERATOR or ADMIN (e.g., if we had a POST /cases/{id}/act)

from app.core.config import settings

P = settings.pagination

@router.get("/cases")
def list_cases(
    skip: int = Query(0, ge=0), 
    limit: int = Query(P.DEFAULT_PAGE_SIZE, ge=1, le=P.MAX_PAGE_SIZE), 
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(READ_ROLES))
):
    query = db.query(RevenueRiskCase)
    if current_user.merchant_id:
        query = query.filter(RevenueRiskCase.merchant_id == current_user.merchant_id)
        
    cases = query.order_by(RevenueRiskCase.created_at.desc()).offset(skip).limit(limit).all()
    return cases

@router.get("/cases/{case_id}")
def get_case(case_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_role(READ_ROLES))):
    query = db.query(RevenueRiskCase).filter(RevenueRiskCase.id == case_id)
    if current_user.merchant_id:
        query = query.filter(RevenueRiskCase.merchant_id == current_user.merchant_id)
        
    case = query.first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case

@router.get("/cases/{case_id}/audit")
def get_case_audit(case_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_role(READ_ROLES))):
    # IDOR Check via get_case
    get_case(case_id, db, current_user)
    return db.query(AuditEvent).filter(AuditEvent.case_id == case_id).order_by(AuditEvent.created_at.desc()).all()

@router.get("/cases/{case_id}/decisions")
def get_case_decisions(case_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_role(READ_ROLES))):
    # IDOR Check via get_case
    get_case(case_id, db, current_user)
    return db.query(CaseDecision).filter(CaseDecision.case_id == case_id).order_by(CaseDecision.created_at.desc()).all()

@router.get("/dashboard/stats")
def get_dashboard_stats(db: Session = Depends(get_db), current_user: User = Depends(require_role(READ_ROLES))):
    query_cases = db.query(RevenueRiskCase)
    if current_user.merchant_id:
        query_cases = query_cases.filter(RevenueRiskCase.merchant_id == current_user.merchant_id)
        
    total_cases = query_cases.with_entities(func.count(RevenueRiskCase.id)).scalar()
    recovered_cases = query_cases.filter(RevenueRiskCase.status == CaseStatus.RECOVERED).with_entities(func.count(RevenueRiskCase.id)).scalar()
    
    total_at_risk = query_cases.with_entities(func.sum(RevenueRiskCase.amount_at_risk)).scalar() or 0
    total_recovered = query_cases.filter(RevenueRiskCase.status == CaseStatus.RECOVERED).with_entities(func.sum(RevenueRiskCase.amount_recovered)).scalar() or 0
    
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
    event_id = request.headers.get("X-Razorpay-Event-Id") or payload.get("id", "unknown_event")

    # 1. Deduplicate Webhook Event (Concurrency protection via UniqueConstraint)
    webhook_record = WebhookEvent(event_id=event_id, event_type=event_type, payload=payload, processed=True)
    db.add(webhook_record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"status": "ok", "message": "duplicate event"}
    
    # Process event
    if event_type in ['payment_link.paid', 'payment_link.partially_paid']:
        ref_id = payload.get("payload", {}).get("payment_link", {}).get("entity", {}).get("reference_id")
        amount_paid = payload.get("payload", {}).get("payment_link", {}).get("entity", {}).get("amount_paid")
        
        if ref_id:
            # Row-level lock to prevent race conditions during updates
            action = db.query(CaseAction).with_for_update().filter_by(idempotency_key=ref_id).first()
            if action and action.status != "SUCCESS":
                case_id = action.case_id
                action.status = "SUCCESS"
                
                case = db.query(RevenueRiskCase).filter_by(id=case_id).first()
                if case and case.status != CaseStatus.RECOVERED:
                    case.transition_to(CaseStatus.RECOVERED)
                    case.amount_recovered = amount_paid
                    db.add(AuditEvent(
                        case_id=case_id,
                        event_type="WEBHOOK_RECEIVED",
                        description=f"Received payment_link.paid for {amount_paid} paise",
                        metadata_blob={"raw": payload}
                    ))
                db.commit()
    return {"status": "ok"}
