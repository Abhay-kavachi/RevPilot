import asyncio
import logging
from sqlalchemy.orm import Session
from app.database.core import SessionLocal
from app.models.domain import RevenueRiskCase, CaseStatus
from app.agent.agent import RevPilotAgent

logger = logging.getLogger(__name__)

class AgentWorker:
    def __init__(self, poll_interval: int = 5):
        self.poll_interval = poll_interval
        self._running = False
        
    async def start(self):
        self._running = True
        logger.info("Starting Agent Background Worker...")
        while self._running:
            try:
                self.process_pending_cases()
            except Exception as e:
                logger.error(f"Error in agent worker loop: {e}")
            
            await asyncio.sleep(self.poll_interval)
            
    def stop(self):
        self._running = False
        logger.info("Stopping Agent Background Worker...")
        
    def process_pending_cases(self):
        """
        Polls the database for cases that need agent attention:
        - OPEN (newly created)
        - REASSESS (webhook outcome failed or expired, needs new plan)
        """
        db: Session = SessionLocal()
        try:
            # For MVP SQLite, we just query. In Postgres, we'd use SELECT FOR UPDATE SKIP LOCKED
            pending_cases = db.query(RevenueRiskCase).filter(
                RevenueRiskCase.status.in_([CaseStatus.OPEN]) # We can add REASSESS if we implement that status
            ).all()
            
            for case in pending_cases:
                logger.info(f"Worker picked up case {case.id} in status {case.status}")
                agent = RevPilotAgent(db)
                agent.process(case.id)
                
        finally:
            db.close()
