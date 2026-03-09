from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pipelines.scheduler import start_scheduler
from routers import products, queue, posting, metrics, onboarding
import logging

logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield

app = FastAPI(title="Operative1 API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router, prefix="/products", tags=["products"])
app.include_router(queue.router, prefix="/queue", tags=["queue"])
app.include_router(posting.router, prefix="/posting", tags=["posting"])
app.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
app.include_router(onboarding.router, prefix="/onboarding", tags=["onboarding"])

@app.get("/health")
def health():
    return {"status": "ok"}
