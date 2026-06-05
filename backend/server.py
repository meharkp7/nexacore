"""
server.py
──────────
FastAPI application — HTTP boundary of the Ramp backend.

Endpoints:
  POST /chat    → main onboarding query
  GET  /health  → liveness probe
"""

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.interfaces import AgentResponse, OnboardingRequest
from backend.agent.agent import get_agent

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Ramp backend starting up...")
    get_agent()  # warm up singleton, validates GROQ_API_KEY early
    logger.info("Agent ready")
    yield
    logger.info("Ramp backend shutting down")


app = FastAPI(
    title="Ramp — Onboarding Agent API",
    description="AI-powered onboarding assistant with Hindsight Memory",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ramp-agent"}


@app.post("/chat", response_model=AgentResponse)
async def chat(request: OnboardingRequest) -> AgentResponse:
    """
    Main onboarding chat endpoint.

    Example request:
    {
        "name": "Priya",
        "team": "Platform Team",
        "role": "Backend Engineer",
        "employee_type": "contractor",
        "query": "What should I do on Day 1?"
    }
    """
    if not request.session_id:
        request.session_id = str(uuid.uuid4())

    try:
        agent = get_agent()
        return await agent.run(request)
    except EnvironmentError as e:
        logger.error("Configuration error: %s", e)
        raise HTTPException(status_code=500, detail=f"Server configuration error: {e}")
    except Exception as e:
        logger.exception("Unexpected error processing chat request")
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")
