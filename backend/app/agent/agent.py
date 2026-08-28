from sqlalchemy.orm import Session
from app.agent.execution_loop import ExecutionLoop

class RevPilotAgent:
    def __init__(self, db: Session):
        self.loop = ExecutionLoop(db)
        
    def process(self, case_id: str):
        """
        Run the agent loop for a specific case.
        """
        self.loop.process_case(case_id)
