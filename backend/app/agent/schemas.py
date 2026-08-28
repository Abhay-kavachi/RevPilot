from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from app.models.domain import CaseStatus

class ActionHistory(BaseModel):
    action_type: str
    status: str
    created_at: datetime
    execution_result: Optional[dict] = None

class AgentContext(BaseModel):
    case_id: str
    case_type: str
    status: CaseStatus
    amount_at_risk: int
    attempt_count: int
    max_attempts: int
    recovery_deadline: Optional[datetime] = None
    action_history: List[ActionHistory] = []
    
    # State tracking
    is_recoverable: bool = True
    requires_approval: bool = False
    
    class Config:
        arbitrary_types_allowed = True
