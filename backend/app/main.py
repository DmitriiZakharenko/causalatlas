"""
CausalAtlas backend — FastAPI entrypoint.

Phase 2: POST /api/pipeline/run now launches a REAL 13-agent pipeline run (via
app/orchestrator.py -> the native `agent00_orchestrator` Claude Code subagent),
persists progress to SQLite, and streams it live over SSE. No more hardcoded
stub responses -- every field returned traces to a real run or a real error.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
from dotenv import load_dotenv

from app import db, eval as eval_mod, graphs as graphs_mod, evidence
from app.agent_registry import AGENT_ORDER
from app.llm_common import get_llm_provider
from app.orchestrator import run_manager, target_scope_label
from app.target_models import AnalysisTargetRequest

app = FastAPI(title="CausalAtlas API", version="0.2.0")

# Local runs should behave like Docker runs: read the ignored repository-level
# .env before the health endpoint or pipeline can resolve the provider.
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)

# Local dev only: frontend (Vite) and backend run on different ports.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PipelineRunRequest(AnalysisTargetRequest):
    autonomy_level: str = "let_it_rip"
    analysis_mode: Literal["graph_only", "full"] = "graph_only"
    execution_profile: Literal["standard", "low_cost"] = "standard"
    dev_pubmed_retmax: int | None = Field(
        default=None,
        description=(
            "Dev-loop-only cost knob: overrides Agent 2's per-year-band PubMed retmax "
            "(default 200, per skills/pubmed-literature-search/SKILL.md) for THIS run "
            "only, to validate the orchestration chain cheaply before a full-cost "
            "demo-quality run. Leave unset for a real/demo run."
        ),
    )


class DecisionRequest(BaseModel):
    decision: str
    note: str | None = None


class JudgeHypothesisRequest(BaseModel):
    hypothesis_id: str
    statement: str
    recombined_edges: list[str] = Field(default_factory=list)


VALID_AUTONOMY_LEVELS = {"autocomplete", "supervised", "let_it_rip"}
VALID_DECISIONS = {"approve", "reject", "edit"}


@app.on_event("startup")
async def _on_startup() -> None:
    await db.init_db()


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "loopfinder-backend",
        "phase": "4-eval-flywheel",
        "llm_provider": get_llm_provider(),
        "pipeline_agents": AGENT_ORDER,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/pipeline/run")
async def start_pipeline_run(req: PipelineRunRequest) -> dict:
    """Launch a real pipeline run. Returns immediately with a `run_id`; the
    caller subscribes to GET /api/pipeline/{run_id}/stream for live progress.
    """
    target = req.resolved_target()
    if req.autonomy_level not in VALID_AUTONOMY_LEVELS:
        raise HTTPException(
            status_code=422,
            detail=f"autonomy_level must be one of {sorted(VALID_AUTONOMY_LEVELS)}",
        )
    retrieval_retmax = req.dev_pubmed_retmax
    if req.execution_profile == "low_cost" and retrieval_retmax is None:
        retrieval_retmax = 5
    run_id = await run_manager.start_run(
        target_scope_label(target),
        target.genes[0] if target.genes else None,
        req.autonomy_level,
        target=target,
        pubmed_retmax_override=retrieval_retmax,
        analysis_mode=req.analysis_mode,
        execution_profile=req.execution_profile,
    )
    return {
        "run_id": run_id,
        "status": "started",
        "disease": target.disease,
        "scope": target_scope_label(target),
        "gene": target.genes[0] if target.genes else None,
        "target": target.model_dump(mode="json"),
        "target_schema_version": target.schema_version,
        "autonomy_level": req.autonomy_level,
        "analysis_mode": req.analysis_mode,
        "execution_profile": req.execution_profile,
        "retrieval_retmax": retrieval_retmax,
        "stream_url": f"/api/pipeline/{run_id}/stream",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/pipeline/{run_id}/decision")
async def submit_pipeline_decision(run_id: str, req: DecisionRequest) -> dict:
    """Phase 3 autonomy control: submit a human approve/reject/edit decision
    for a run that is currently `paused` at a checkpoint (per its
    `autonomy_level` -- see agents/agent00_orchestrator/AGENTS.md), resuming
    its SAME claude session with the decision as the next input.
    """
    if req.decision not in VALID_DECISIONS:
        raise HTTPException(
            status_code=422, detail=f"decision must be one of {sorted(VALID_DECISIONS)}"
        )
    run = await db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"no run found with id {run_id}")
    if run["status"] != "paused":
        raise HTTPException(
            status_code=409,
            detail=f"run {run_id} is not paused (status={run['status']!r}) -- nothing to decide on",
        )
    try:
        await run_manager.resume_run(run_id, req.decision, req.note)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "run_id": run_id,
        "status": "resumed",
        "decision": req.decision,
        "stream_url": f"/api/pipeline/{run_id}/stream",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/pipeline/{run_id}/retry")
async def retry_pipeline_run(run_id: str) -> dict:
    """Continue a `failed` run's same claude session instead of restarting
    from Agent 1 -- see `RunManager.retry_run`'s docstring for why this is
    distinct from the `paused`-only `/decision` endpoint above."""
    run = await db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"no run found with id {run_id}")
    if run["status"] != "failed":
        raise HTTPException(
            status_code=409,
            detail=f"run {run_id} is not failed (status={run['status']!r}) -- nothing to retry",
        )
    try:
        await run_manager.retry_run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "run_id": run_id,
        "status": "retrying",
        "stream_url": f"/api/pipeline/{run_id}/stream",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/pipeline/{run_id}/cancel")
async def cancel_pipeline_run(run_id: str) -> dict:
    try:
        await run_manager.cancel_run(run_id)
    except ValueError as exc:
        message = str(exc)
        status = 404 if "no run found" in message else 409
        raise HTTPException(status_code=status, detail=message) from exc
    return {"run_id": run_id, "status": "cancelled", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/pipeline/{run_id}/status")
async def get_run_status(run_id: str) -> dict:
    run = await db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"no run found with id {run_id}")
    run["interventions"] = await db.get_human_interventions(run_id)
    # Status is polled during SSE updates. Avoid rescanning the historical
    # novelty corpus and large Codex transcripts on every progress event.
    run["evidence_summary"] = evidence.summarize_run(run, include_catalog=False)
    return run


@app.get("/api/pipeline/runs")
async def list_pipeline_runs() -> dict:
    runs = await db.list_runs()
    # The launch page polls this endpoint frequently. Keep it lightweight;
    # historical novelty-catalog aggregation belongs to /api/evidence/{run_id}.
    return {
        "runs": [
            {**run, "evidence_summary": evidence.summarize_run(run, include_catalog=False)}
            for run in runs
        ]
    }


@app.get("/api/evidence/{run_id}")
async def get_evidence_summary(run_id: str) -> dict:
    run = await db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"no run found with id {run_id}")
    return evidence.summarize_run(run)


@app.get("/api/demo/replay")
async def get_demo_replay() -> dict:
    """Read-only replay metadata from the completed persisted IPF+IL11 run."""
    return evidence.demo_summary()


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


@app.get("/api/graphs")
async def list_graphs() -> dict:
    return {"graphs": graphs_mod.list_available_graphs()}


@app.get("/api/graphs/{disease_slug}")
async def get_graph(disease_slug: str) -> dict:
    try:
        return graphs_mod.load_graph_for_ui(disease_slug)
    except graphs_mod.GraphNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/eval/backfill")
async def run_eval_backfill() -> dict:
    """Phase 4: recompute `historical_backfill` eval_scores from the REAL
    Session 001-003 files already on disk (see app/eval.py's module
    docstring) -- pure, deterministic, zero-cost, idempotent. Safe to call
    any time; never touches the `claude` CLI.
    """
    records = await eval_mod.backfill_historical_sessions()
    return {"scored": len(records), "records": records}


@app.get("/api/eval/dashboard")
async def get_eval_dashboard(subject_type: str | None = None) -> dict:
    records = await db.list_eval_scores(subject_type=subject_type)
    return eval_mod.compute_dashboard_metrics(records)


@app.get("/api/eval/scores")
async def list_eval_scores(subject_type: str | None = None, session_id: str | None = None) -> dict:
    return {"scores": await db.list_eval_scores(subject_type=subject_type, session_id=session_id)}


@app.post("/api/eval/judge/{run_id}")
async def trigger_live_judge(run_id: str, req: JudgeHypothesisRequest) -> dict:
    """Phase 4: dispatch the independent `agent14_eval_judge` against ONE
    hypothesis from an already-completed run. A REAL, subscription-billed
    `claude` CLI invocation -- unlike `/api/eval/backfill`, this has a real
    cost and must only be triggered on explicit request (e.g. from a future
    UI's "run independent audit" button), never automatically or in a loop.
    """
    run = await db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"no run found with id {run_id}")
    if run["status"] != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"run {run_id} is not completed yet (status={run['status']!r}) -- nothing to audit",
        )
    verdict = await eval_mod.run_live_judge(
        run_id, req.hypothesis_id, req.statement, req.recombined_edges
    )
    return {"run_id": run_id, "hypothesis_id": req.hypothesis_id, "verdict": verdict}
