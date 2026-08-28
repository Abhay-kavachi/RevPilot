from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import router as api_router
from app.agent.worker import AgentWorker
import asyncio
from contextlib import asynccontextmanager

worker = AgentWorker(poll_interval=5)

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

@app.get("/health")
def health_check():
    return {"status": "healthy"}
