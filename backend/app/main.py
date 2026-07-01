"""
LoopFinder backend — FastAPI entrypoint.

Phase 0 scope only: health check + a hardcoded stub for POST /api/pipeline/run,
proving frontend<->backend wiring before any real agent logic exists (Phase 2).
"""
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="LoopFinder API", version="0.0.1")

# Local dev only: frontend (Vite) and backend run on different ports.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PipelineRunRequest(BaseModel):
    disease: str
    gene: str | None = None
    autonomy_level: str = "let_it_rip"


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "loopfinder-backend",
        "phase": "0-scaffold",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/pipeline/run")
async def run_pipeline_stub(req: PipelineRunRequest) -> dict:
    """
    Phase 0 stub only. Returns a hardcoded fake response so the frontend wiring
    can be proven end-to-end before Phase 2 replaces this with the real
    12-agent orchestrator (see backend/orchestrator.py, added in Phase 2).
    """
    return {
        "run_id": "stub-run-0000",
        "status": "stub_not_implemented",
        "note": (
            "This is a hardcoded Phase 0 placeholder, not a real pipeline run. "
            "Real orchestration lands in Phase 2."
        ),
        "echo": req.model_dump(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
