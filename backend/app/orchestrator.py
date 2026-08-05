"""
Phase 2: pipeline orchestration.

The actual 13-agent sequencing/dispatch logic lives in the `agent00_orchestrator`
native Claude Code subagent (see agents/agent00_orchestrator/AGENTS.md) -- it uses
its own Task tool to dispatch each pipeline agent and its own Skill tool to load
skills before each dispatch, per the "lean on Claude Code's native subagent/skill
system, minimize custom orchestration" decision (see chat history).

This module's job is everything AROUND that single CLI invocation:
- build the top-level prompt handed to the orchestrator agent
- create/locate the session folder and detect non-destructive-merge situations
- run the orchestrator via `claude_cli.run_orchestrator_stream` and translate its
  raw stream-json lines into the small set of UI-facing progress events the
  frontend's live progress view (Phase 5) subscribes to
- persist every event to SQLite (durable audit trail + eval flywheel input) and
  fan it out to any live SSE subscribers

Never fabricates progress: every `agent_started`/`agent_completed`/`skill_loaded`
event corresponds to a real `Task`/`Skill` tool_use (and matching tool_result)
that actually appeared in the orchestrator's real stream-json output.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app import db, llm_cli as claude_cli
from app.agent_registry import AGENT_ORDER
from app.target_models import AnalysisTarget
from app.entity_normalization import normalize_target_dimensions
from app.drug_knowledge import normalize_drug
from app.context_models import StructuredContext

# Phase 3: the exact machine-parseable marker agent00_orchestrator's AGENTS.md
# instructs it to print (as the first line of its final text response) when
# an autonomy-pause checkpoint is reached. Kept as one shared constant so the
# translator's parsing and the AGENTS.md doc can't silently drift apart.
PAUSE_MARKER = "PAUSED_FOR_APPROVAL:"

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SESSIONS_DIR = REPO_ROOT / "data" / "sessions"
GRAPHS_DIR = REPO_ROOT / "data" / "graphs"


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "target"


def make_run_id(disease: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{slugify(disease)}_{ts}"


def target_scope_label(target: AnalysisTarget) -> str:
    """Return a persistence/search scope without fabricating a disease."""
    if target.disease:
        return target.disease
    genes = "_".join(target.genes) or "any_gene"
    drugs = "_".join(target.drugs) or "any_drug"
    return f"gene_drug_{genes}_{drugs}"


def session_dir_for(run_id: str) -> Path:
    d = SESSIONS_DIR / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _artifact_cache_key(target: AnalysisTarget, execution_profile: str, retmax: int | None) -> str:
    payload = {
        "schema_version": target.schema_version,
        "target": target.model_dump(mode="json"),
        "execution_profile": execution_profile,
        "retrieval_retmax": retmax,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


async def _reuse_compatible_artifacts(
    *, target: AnalysisTarget, execution_profile: str, retmax: int | None, session_dir: Path, current_run_id: str
) -> dict | None:
    """Copy only exact-target, completed-run inputs into a new low-cost run."""
    if execution_profile != "low_cost":
        return None
    cache_key = _artifact_cache_key(target, execution_profile, retmax)
    runs = await db.list_runs()
    completed_ids = {str(run.get("run_id")) for run in runs if run.get("status") == "completed"}
    candidates = sorted(SESSIONS_DIR.iterdir(), key=lambda path: path.stat().st_mtime, reverse=True) if SESSIONS_DIR.exists() else []
    reusable = {"canonical_baseline.json", "publications_raw.json", "publications_verified.json", "quality_scores.json",
                "publications_verified_compact.json", "quality_scores_compact.json"}
    for source_dir in candidates:
        if not source_dir.is_dir() or source_dir.name in {current_run_id} or source_dir.name not in completed_ids:
            continue
        manifest_path = source_dir / "analysis_target.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text())
        except Exception:  # noqa: BLE001
            continue
        if manifest.get("cache_key") != cache_key:
            continue
        copied = []
        for name in sorted(reusable):
            source = source_dir / name
            if source.exists():
                shutil.copy2(source, session_dir / name)
                copied.append(name)
        if copied:
            result = {
                "schema_version": "artifact-cache.v1",
                "cache_key": cache_key,
                "source_run_id": source_dir.name,
                "artifacts": copied,
                "reuse_policy": "exact_target_profile_and_retrieval_budget",
            }
            (session_dir / "cache_manifest.json").write_text(json.dumps(result, indent=2) + "\n")
            return result
    return None


def existing_graph_path(disease: str) -> Path | None:
    path = GRAPHS_DIR / slugify(disease) / "knowledge_graph.json"
    return path if path.exists() else None


def build_orchestrator_prompt(
    *,
    run_id: str,
    disease: str,
    gene: str | None,
    autonomy_level: str,
    session_dir: Path,
    target: AnalysisTarget | None = None,
    pubmed_retmax_override: int | None = None,
    analysis_mode: str = "graph_only",
    execution_profile: str = "standard",
    cache_manifest: dict | None = None,
) -> str:
    merge_note = ""
    prior_graph = existing_graph_path(disease)
    if prior_graph is not None:
        try:
            prior_graph_display = prior_graph.relative_to(REPO_ROOT)
        except ValueError:
            prior_graph_display = prior_graph
        merge_note = (
            f"\nA knowledge graph for this disease ALREADY EXISTS at "
            f"{prior_graph_display}. Per your hard constraints, Agent 6's "
            f"dispatch for this run MUST be told to non-destructively MERGE new nodes/edges "
            f"into it -- never overwrite or delete existing provenance."
        )
    else:
        merge_note = (
            f"\nNo prior knowledge graph exists yet for this disease -- Agent 6 will create "
            f"one fresh at data/graphs/{slugify(disease)}/knowledge_graph.json."
        )
    target = target or AnalysisTarget(disease=disease, genes=[gene] if gene else [])
    gene_line = f"gene: {gene}" if gene else "gene: (none specified -- disease-wide target)"
    retmax_note = ""
    if pubmed_retmax_override is not None:
        retmax_note = (
            f"\nCOST-SCOPED DEV-LOOP RUN: for this run only, tell Agent 2 to use "
            f"retmax={pubmed_retmax_override} per year-band for its PubMed E-utilities "
            f"esearch calls (per pubmed-literature-search), instead of the skill's normal "
            f"default of 200 -- this run is for validating the full orchestration chain "
            f"end-to-end cheaply, not for demo-quality corpus size. Do not change the "
            f"skill file itself; this override applies to this run's Agent 2 dispatch only."
        )
    profile_note = ""
    if execution_profile == "low_cost":
        profile_note = (
            "\nLOW-COST PROFILE: keep graph_only mode; use at most 3 complementary retrieval "
            "strategies, retmax from the run setting per year-band, and no node-expansion "
            "queries. Use compact upstream files for Agents 3-5. Do not run novelty, "
            "hypothesis, peer-review, or experiment-design stages. Preserve every strict "
            "PMID/sentence/provenance quality gate."
        )
    cache_note = ""
    if cache_manifest:
        cache_note = (
            f"\nCOMPATIBLE ARTIFACT CACHE: read-only inputs were copied from completed run "
            f"{cache_manifest['source_run_id']} into this session. Reuse the listed artifacts "
            "and do not repeat retrieval or verification unless an artifact is missing. "
            "Retain the current run_id in all newly written outputs."
        )
    return f"""Run the full 13-agent pipeline for this target:

run_id: {run_id}
disease: {disease}
{gene_line}
target_schema_version: {target.schema_version}
target_json: {json.dumps(target.model_dump(mode="json"), separators=(",", ":"))}
autonomy_level: {autonomy_level}
analysis_mode: {analysis_mode}
execution_profile: {execution_profile}
session output directory (absolute): {session_dir}
{merge_note}
{retmax_note}
{profile_note}
{cache_note}

Follow your AGENTS.md exactly. In `graph_only` mode, dispatch only Agents 1 through 09,
then stop after graph, semantic validation, topology, contradiction and gap analysis;
do not run novelty, hypothesis, peer-review or experiment-design stages. In `full` mode,
dispatch Agents 1 through 13 in order via the Task tool.
load each dispatch's relevant skill(s) via the Skill tool immediately before dispatching
per skills/skills_manifest.json, persist every agent's raw output to
{session_dir}/agent<NN>_output.json immediately after it completes, and assemble the
mandatory session files. Do not fabricate any agent's output if its Task dispatch fails --
report the failure explicitly and stop.
"""


def _extract_agent_name(tool_input: dict) -> str:
    candidate = tool_input.get("subagent_type")
    if isinstance(candidate, str) and candidate in AGENT_ORDER:
        return candidate
    haystack = f"{tool_input.get('description', '')} {tool_input.get('prompt', '')}"
    for name in AGENT_ORDER:
        if name in haystack:
            return name
    return candidate or "unknown_agent"


def _walk_blocks(node, tool_uses: list[dict], tool_results: list[dict]) -> None:
    """Recursively find every `tool_use`/`tool_result` block nested anywhere in
    a raw claude stream-json event. Deliberately NOT a shallow
    `event["message"]["content"]` lookup: empirically (Phase 2 live smoke
    test), the orchestrator's own Task-dispatch tool_result did not always
    show up at that fixed shape/depth -- the same recursive-walk approach
    already proven in test_agent10_novelty.py's `_tool_uses` helper is used
    here for both block types, since it is robust to exactly this kind of
    stream-json shape variation.
    """
    if isinstance(node, dict):
        btype = node.get("type")
        if btype == "tool_use":
            tool_uses.append(node)
        elif btype == "tool_result":
            tool_results.append(node)
        for value in node.values():
            _walk_blocks(value, tool_uses, tool_results)
    elif isinstance(node, list):
        for value in node:
            _walk_blocks(value, tool_uses, tool_results)


def _summarize_tool_result(content) -> str:
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
        text = " ".join(parts) if parts else str(content)
    else:
        text = str(content)
    text = text.strip()
    return text[:800] + ("..." if len(text) > 800 else "")


class StreamTranslator:
    """Stateful translator: raw claude stream-json line -> 0+ UI progress events.

    Statefulness is required to pair a `Task`/`Skill` tool_use with its later
    `tool_result` (matched by `tool_use_id`), which is how `agent_completed` is
    derived from real data rather than assumed.
    """

    def __init__(self) -> None:
        self._pending: dict[str, dict] = {}

    def feed(self, raw: dict) -> list[dict]:
        rtype = raw.get("type")

        if rtype in ("agent_failed", "orchestrator_failed"):
            return [
                {
                    "type": "run_failed",
                    "reason": raw.get("stderr", "")[-2000:],
                    "returncode": raw.get("returncode"),
                }
            ]

        if rtype == "result":
            if raw.get("is_error"):
                return [{"type": "run_failed", "reason": raw.get("result", "unknown error")}]
            result_text = raw.get("result", "")
            if result_text.lstrip().startswith(PAUSE_MARKER):
                # Per agent00_orchestrator/AGENTS.md's autonomy-pause protocol:
                # the orchestrator ends its turn (the CLI process exits 0)
                # rather than continuing to dispatch, with this exact marker
                # as the first line -- distinguishing a deliberate pause from
                # genuine completion, which otherwise look identical (both
                # are a non-error "result" event).
                reason = result_text.split(PAUSE_MARKER, 1)[1].strip()
                agent = reason.split("\u2014", 1)[0].strip(" -:") or None
                return [{"type": "run_paused", "agent": agent, "reason": reason}]
            usage = raw.get("usage") if isinstance(raw.get("usage"), dict) else {}

            def _usage_value(key: str):
                return raw.get(key, usage.get(key))

            event = {
                    "type": "run_completed",
                    "cost_usd": raw.get("total_cost_usd", raw.get("cost_usd")),
                    "duration_ms": raw.get("duration_ms"),
                    "input_tokens": _usage_value("input_tokens"),
                    "output_tokens": _usage_value("output_tokens"),
                    "cached_input_tokens": _usage_value("cached_input_tokens"),
                    "reasoning_tokens": _usage_value("reasoning_tokens"),
                    "total_tokens": _usage_value("total_tokens"),
                    "usage_source": raw.get("usage_source", usage.get("usage_source")),
                    "llm_calls": raw.get("calls"),
                    "result_text": result_text,
                }
            return [{key: value for key, value in event.items() if value is not None}]

        tool_uses: list[dict] = []
        tool_results: list[dict] = []
        _walk_blocks(raw, tool_uses, tool_results)
        if not tool_uses and not tool_results:
            return []

        events: list[dict] = []

        for block in tool_uses:
            name = block.get("name")
            tool_input = block.get("input") or {}
            tool_id = block.get("id")
            if not tool_input:
                # With `--include-partial-messages`, each tool_use fires twice:
                # once as `content_block_start` with a placeholder empty
                # `input: {}` (before its arguments have streamed in), and once
                # fully populated in the final complete assistant message.
                # Empirically (Phase 2 live smoke test), skipping the empty
                # one is what prevents duplicate/junk "unknown_skill" and
                # "unknown_agent" events from reaching the UI.
                continue
            if name == "Skill":
                skill_name = tool_input.get("skill") or tool_input.get("name") or "unknown_skill"
                events.append({"type": "skill_loaded", "skill": skill_name})
            elif name in ("Task", "Agent"):
                # Empirically (Phase 2 live smoke test, 2026-07-01): this Claude
                # Code CLI version dispatches subagents via a tool literally
                # named "Agent" (with `subagent_type`/`description`/`prompt`
                # input fields), not "Task" -- despite "Task" being the name
                # used throughout this project's AGENTS.md docs and being one
                # of the tools listed in the CLI's own init event capability
                # list. Handling both names is deliberate, not a guess: only
                # "Agent" was ever observed actually being invoked in practice.
                agent_name = _extract_agent_name(tool_input)
                if tool_id:
                    self._pending[tool_id] = {"agent": agent_name}
                events.append(
                    {
                        "type": "agent_started",
                        "agent": agent_name,
                        "description": tool_input.get("description", ""),
                    }
                )

        for block in tool_results:
            tool_use_id = block.get("tool_use_id")
            pending = self._pending.pop(tool_use_id, None) if tool_use_id else None
            if pending:
                events.append(
                    {
                        "type": "agent_completed",
                        "agent": pending["agent"],
                        "is_error": bool(block.get("is_error", False)),
                        "summary": _summarize_tool_result(block.get("content")),
                    }
                )

        return events


class RunManager:
    """In-process registry of live runs: one background asyncio task + a set of
    SSE subscriber queues per run_id. SQLite (see app/db.py) is the durable
    record; the queues only exist to push new events to connected clients
    without polling.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    def _subs(self, run_id: str) -> list[asyncio.Queue]:
        return self._subscribers.setdefault(run_id, [])

    async def _publish(self, run_id: str, seq: int, event: dict, *, created_at: float) -> None:
        payload = {"seq": seq, "created_at": created_at, **event}
        for q in list(self._subs(run_id)):
            await q.put(payload)

    async def _finish(self, run_id: str) -> None:
        for q in list(self._subs(run_id)):
            await q.put(None)

    async def start_run(
        self,
        disease: str,
        gene: str | None,
        autonomy_level: str,
        *,
        target: AnalysisTarget | None = None,
        pubmed_retmax_override: int | None = None,
        analysis_mode: str = "graph_only",
        execution_profile: str = "standard",
    ) -> str:
        target = target or AnalysisTarget(disease=disease, genes=[gene] if gene else [])
        scope = target_scope_label(target)
        run_id = make_run_id(scope)
        session_dir = session_dir_for(run_id)
        (session_dir / "analysis_target.json").write_text(
            json.dumps(
                {
                    "schema_version": target.schema_version,
                    "target": target.model_dump(mode="json"),
                    "normalized_dimensions": {
                        "genes": normalize_target_dimensions(target.genes, "gene"),
                        "drugs": normalize_target_dimensions(target.drugs, "drug"),
                        "tissues": normalize_target_dimensions(target.tissues, "tissue"),
                        "cell_types": normalize_target_dimensions(target.cell_types, "cell_type"),
                    },
                    "legacy_request": {"disease": target.disease, "gene": gene},
                    "analysis_mode": analysis_mode,
                    "execution_profile": execution_profile,
                    "cache_key": _artifact_cache_key(target, execution_profile, pubmed_retmax_override),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        (session_dir / "drug_knowledge.json").write_text(
            json.dumps(
                {
                    "schema_version": "drug-knowledge.v1",
                    "status": "input_only",
                    "drugs": [normalize_drug(drug).model_dump(mode="json") for drug in target.drugs],
                    "claims": [],
                    "note": "No drug claim is asserted until a verified provider or publication supplies provenance.",
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        (session_dir / "target_context.json").write_text(
            json.dumps(
                {
                    "schema_version": "context.v1",
                    "context": StructuredContext.from_raw({
                        "tissue": target.tissues[0] if target.tissues else None,
                        "cell_type": target.cell_types[0] if target.cell_types else None,
                    }).model_dump(mode="json"),
                    "all_tissues": target.tissues,
                    "all_cell_types": target.cell_types,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        # Generated up front (not parsed back out of the first stream event)
        # so it's known before the process even starts, and so a run that
        # pauses before producing any events still has a resumable session_id
        # on file.
        session_id = str(uuid.uuid4())
        target_json = json.dumps(target.model_dump(mode="json"), sort_keys=True)
        await db.create_run(
            run_id,
            scope,
            gene,
            autonomy_level,
            session_id=session_id,
            target_schema_version=target.schema_version,
            target_json=target_json,
        )
        cache_manifest = await _reuse_compatible_artifacts(
            target=target,
            execution_profile=execution_profile,
            retmax=pubmed_retmax_override,
            session_dir=session_dir,
            current_run_id=run_id,
        )
        prompt = build_orchestrator_prompt(
            run_id=run_id,
            disease=scope,
            gene=gene,
            autonomy_level=autonomy_level,
            session_dir=session_dir,
            target=target,
            pubmed_retmax_override=pubmed_retmax_override,
            analysis_mode=analysis_mode,
            execution_profile=execution_profile,
            cache_manifest=cache_manifest,
        )
        stream = claude_cli.run_orchestrator_stream(prompt, session_id=session_id)
        task = asyncio.create_task(self._run(run_id, stream))
        self._tasks[run_id] = task
        return run_id

    async def resume_run(self, run_id: str, decision: str, note: str | None = None) -> None:
        """Phase 3: continue a `paused` run's SAME claude session after a human
        approve/reject/edit decision, per agent00_orchestrator/AGENTS.md's
        autonomy-pause protocol. Raises ValueError if the run isn't actually
        paused (callers -- see main.py -- turn that into an HTTP 409)."""
        run = await db.get_run(run_id)
        if run is None:
            raise ValueError(f"no run found with id {run_id}")
        if run["status"] != "paused":
            raise ValueError(f"run {run_id} is not paused (status={run['status']!r})")
        if not run["session_id"]:
            raise ValueError(f"run {run_id} has no session_id on file -- cannot resume")

        await db.record_human_intervention(run_id, run["current_agent"] or "unknown", decision, note)
        resume_prompt = (
            f"HUMAN DECISION for the paused checkpoint at {run['current_agent']}: "
            f"{decision.upper()}."
            + (f" Note: {note}" if note else "")
            + " Continue the pipeline per your AGENTS.md autonomy-pause rules -- if REJECT, "
            "do not proceed past this checkpoint as originally planned; ask what to do "
            "differently instead of retrying the identical action."
        )
        stream = claude_cli.run_orchestrator_stream(
            resume_prompt, session_id=run["session_id"], resume=True
        )
        await db.update_run_status(run_id, "running")
        task = asyncio.create_task(self._run(run_id, stream))
        self._tasks[run_id] = task

    async def retry_run(self, run_id: str) -> None:
        """Continue a `failed` run's SAME claude session (`--resume`) instead of
        starting over from Agent 1.

        Found necessary live (2026-07-05): a run that fails mid-pipeline for a
        transient reason -- most commonly the subscription's rolling usage cap
        (`rate_limit_event` in the raw stream, resets on its own after the
        window) rather than a real bug -- had no way to continue, because
        `resume_run` above only accepts `status == "paused"` (a deliberate
        autonomy checkpoint, semantically different from an involuntary
        failure: there's no human decision to record here, just "try again").
        Safe to expose unconditionally rather than trying to auto-detect
        "was this a rate limit": `--session-id` was used (never
        `--no-session-persistence`) for every run, so the underlying
        conversation -- including whatever any already-completed agents wrote
        to `data/sessions/<run_id>/` -- is genuinely still on disk to resume
        into; if the failure wasn't transient, retrying just fails again
        instead of silently fabricating progress.
        """
        run = await db.get_run(run_id)
        if run is None:
            raise ValueError(f"no run found with id {run_id}")
        if run["status"] != "failed":
            raise ValueError(f"run {run_id} is not failed (status={run['status']!r}) -- nothing to retry")
        if not run["session_id"]:
            raise ValueError(f"run {run_id} has no session_id on file -- cannot retry")

        retry_prompt = (
            f"The previous attempt was interrupted before completion (recorded reason: "
            f"{run['error'] or 'unknown'}). Check data/sessions/{run_id}/ for any agent "
            "outputs already written, then continue the pipeline from the next required "
            "step per your AGENTS.md -- do not re-run an agent whose output file already "
            "exists and looks complete, and do not fabricate results for a step that "
            "hasn't actually run yet."
        )
        stream = claude_cli.run_orchestrator_stream(retry_prompt, session_id=run["session_id"], resume=True)
        # NOTE: update_run_status's COALESCE(NULLIF(?, ''), error) deliberately
        # never clears a previously recorded error (see its docstring) -- the
        # prior failure reason stays visible in `status.error` as history even
        # while `status` flips back to "running", rather than disappearing.
        await db.update_run_status(run_id, "running")
        task = asyncio.create_task(self._run(run_id, stream))
        self._tasks[run_id] = task

    async def cancel_run(self, run_id: str) -> None:
        """Stop a live run and mark it terminal without pretending it failed."""
        run = await db.get_run(run_id)
        if run is None:
            raise ValueError(f"no run found with id {run_id}")
        if run["status"] not in {"pending", "running", "paused"}:
            raise ValueError(f"run {run_id} is not active (status={run['status']!r})")
        task = self._tasks.get(run_id)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        reason = "Cancelled by user"
        await db.update_run_status(run_id, "cancelled", error=reason)
        event = {"type": "run_cancelled", "reason": reason}
        seq, created_at = await db.append_event(run_id, "run_cancelled", event)
        await self._publish(run_id, seq, event, created_at=created_at)
        await self._finish(run_id)
        self._tasks.pop(run_id, None)

    async def _run(self, run_id: str, stream) -> None:
        translator = StreamTranslator()
        terminal_types = ("run_completed", "run_failed")
        terminal_emitted = False
        try:
            async for raw_event in stream:
                for ui_event in translator.feed(raw_event):
                    etype = ui_event["type"]
                    if etype in terminal_types:
                        if terminal_emitted:
                            # claude_cli can legitimately emit a second terminal
                            # event for the same run (e.g. a "result" event
                            # reporting the real failure reason, immediately
                            # followed by a synthetic `orchestrator_failed`
                            # wrapper once the process actually exits non-zero,
                            # usually with an empty/redundant stderr). Only the
                            # FIRST terminal event is real signal; discovered
                            # live via a real subscription rate-limit hit
                            # during Phase 2 dev-loop testing, where the second,
                            # empty-reason event was clobbering the first,
                            # informative one both in the DB and the SSE feed.
                            continue
                        terminal_emitted = True
                    # Status is always updated BEFORE the corresponding event is
                    # appended/published -- any subscriber that observes the
                    # event (via DB replay or the live queue) is therefore
                    # guaranteed to see the up-to-date `runs.status` if it
                    # queries it right after, with no race window.
                    if etype == "agent_started":
                        await db.update_run_status(run_id, "running", current_agent=ui_event["agent"])
                    elif etype == "run_completed":
                        await db.update_run_status(run_id, "completed")
                    elif etype == "run_failed":
                        await db.update_run_status(
                            run_id, "failed", error=str(ui_event.get("reason", ""))[:2000]
                        )
                    elif etype == "run_paused":
                        # NOT in `terminal_types`: unlike completed/failed, more
                        # events legitimately arrive later, once `resume_run`
                        # starts a fresh `_run` task for the same run_id after
                        # a human decision comes in.
                        await db.update_run_status(
                            run_id, "paused", current_agent=ui_event.get("agent")
                        )
                    seq, created_at = await db.append_event(run_id, etype, ui_event)
                    await self._publish(run_id, seq, ui_event, created_at=created_at)
        except Exception as exc:  # noqa: BLE001 -- must surface, never swallow
            if not terminal_emitted:
                await db.update_run_status(run_id, "failed", error=str(exc)[:2000])
                err_event = {"type": "run_failed", "reason": str(exc)}
                seq, created_at = await db.append_event(run_id, "run_failed", err_event)
                await self._publish(run_id, seq, err_event, created_at=created_at)
        finally:
            await self._finish(run_id)

    async def subscribe(self, run_id: str, after_seq: int = -1):
        """Async generator: replays persisted history from `after_seq`, then
        yields live events as they're published, until the run finishes."""
        q: asyncio.Queue = asyncio.Queue()
        self._subs(run_id).append(q)
        seen: set[int] = set()
        terminal_types = ("run_completed", "run_failed")
        try:
            history = await db.get_events_since(run_id, after_seq)
            run_row = await db.get_run(run_id)
            # Retried runs keep old run_failed events in the append-only log while
            # `runs.status` flips back to "running" -- discovered live (2026-07-05)
            # when the UI refreshed mid-retry and showed every prior failure at
            # once, then stopped receiving live events because ANY historical
            # terminal event incorrectly set `already_finished`.
            if run_row and run_row["status"] in ("running", "paused"):
                already_finished = False
            elif history:
                already_finished = (
                    history[-1]["event_type"] in terminal_types
                    and run_row is not None
                    and run_row["status"] in ("completed", "failed")
                )
            else:
                # Status may flip to failed/completed before the terminal row is
                # appended -- keep listening so the in-flight event isn't dropped.
                already_finished = False
            for ev in history:
                seen.add(ev["seq"])
                yield {
                    "seq": ev["seq"],
                    "type": ev["event_type"],
                    "created_at": ev["created_at"],
                    **ev["payload"],
                }
            # If the terminal event is already in the replayed history, the run
            # is fully done and no more events will EVER be appended (`_run`
            # appends exactly one terminal event, always last) -- safe to stop
            # without touching the queue. If it's NOT in history yet, the queue
            # (registered above, before this read) is guaranteed to eventually
            # receive it, even if the run finished in the gap between the read
            # and here -- so falling through to the wait loop below is always
            # correct and never hangs. (A separate `db.get_run(...)` status
            # check here would race: the terminal event could already be
            # sitting in the queue while `status` briefly reads as terminal,
            # and returning early would silently drop it.)
            if already_finished:
                return
            while True:
                item = await q.get()
                if item is None:
                    break
                if item["seq"] in seen:
                    continue
                seen.add(item["seq"])
                yield item
                if item["type"] in terminal_types:
                    break
        finally:
            subs = self._subs(run_id)
            if q in subs:
                subs.remove(q)


run_manager = RunManager()
