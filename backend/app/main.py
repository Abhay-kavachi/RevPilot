from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import router as api_router
from app.agent.worker import AgentWorker
import asyncio
from contextlib import asynccontextmanager
from app.core.config import settings

worker = AgentWorker(poll_interval=settings.WORKER_POLL_INTERVAL)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the worker in the background
    task = asyncio.create_task(worker.start())
    yield
    # Stop the worker
    worker.stop()
    await task

app = FastAPI(title="RevPilot API", description="AI Revenue Recovery System", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

# The user configured the webhook to point to /webhook/razorpay, 
# so we add an alias router here for convenience.
from app.api.endpoints import razorpay_webhook, get_db
from fastapi import Request, Depends
from sqlalchemy.orm import Session

@app.post("/webhook/razorpay")
async def root_razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    return await razorpay_webhook(request, db)

@app.get("/health")
def health_check():
    return {"status": "healthy"}
