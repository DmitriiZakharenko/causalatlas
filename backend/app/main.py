"""
LoopFinder backend — FastAPI entrypoint.

Phase 2: POST /api/pipeline/run now launches a REAL 13-agent pipeline run (via
app/orchestrator.py -> the native `agent00_orchestrator` Claude Code subagent),
persists progress to SQLite, and streams it live over SSE. No more hardcoded
stub responses -- every field returned traces to a real run or a real error.
"""
import json
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app import db
from app.agent_registry import AGENT_ORDER
from app.orchestrator import run_manager

app = FastAPI(title="LoopFinder API", version="0.2.0")

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
    dev_pubmed_retmax: int | None = Field(
        default=None,
        description=(
            "Dev-loop-only cost knob: overrides Agent 2's per-year-band PubMed retmax "
            "(default 200, per skills/pubmed-literature-search/SKILL.md) for THIS run "
            "only, to validate the orchestration chain cheaply before a full-cost "
            "demo-quality run. Leave unset for a real/demo run."
        ),
    )


VALID_AUTONOMY_LEVELS = {"autocomplete", "supervised", "let_it_rip"}


@app.on_event("startup")
async def _on_startup() -> None:
    await db.init_db()


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "loopfinder-backend",
        "phase": "2-pipeline-orchestration",
        "pipeline_agents": AGENT_ORDER,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/pipeline/run")
async def start_pipeline_run(req: PipelineRunRequest) -> dict:
    """Launch a real pipeline run. Returns immediately with a `run_id`; the
    caller subscribes to GET /api/pipeline/{run_id}/stream for live progress.
    """
    if not req.disease or not req.disease.strip():
        raise HTTPException(status_code=422, detail="disease is required")
    if req.autonomy_level not in VALID_AUTONOMY_LEVELS:
        raise HTTPException(
            status_code=422,
            detail=f"autonomy_level must be one of {sorted(VALID_AUTONOMY_LEVELS)}",
        )
    run_id = await run_manager.start_run(
        req.disease.strip(),
        req.gene,
        req.autonomy_level,
        pubmed_retmax_override=req.dev_pubmed_retmax,
    )
    return {
        "run_id": run_id,
        "status": "started",
        "disease": req.disease.strip(),
        "gene": req.gene,
        "autonomy_level": req.autonomy_level,
        "stream_url": f"/api/pipeline/{run_id}/stream",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/pipeline/{run_id}/status")
async def get_run_status(run_id: str) -> dict:
    run = await db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"no run found with id {run_id}")
    return run


@app.get("/api/pipeline/runs")
async def list_pipeline_runs() -> dict:
    return {"runs": await db.list_runs()}


@app.get("/api/pipeline/{run_id}/stream")
async def stream_pipeline_run(run_id: str, after_seq: int = -1):
    """Server-Sent Events stream of real progress events (`agent_started`,
    `agent_completed`, `skill_loaded`, `run_completed`, `run_failed`) for one
    run. `after_seq` lets a reconnecting client resume without re-reading
    history it already has.
    """
    run = await db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"no run found with id {run_id}")

    async def event_generator():
        async for event in run_manager.subscribe(run_id, after_seq):
            yield {"event": event.get("type", "message"), "data": json.dumps(event)}

    return EventSourceResponse(event_generator())
