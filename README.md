# LoopFinder

A full-stack vertical AI agent product: ingests a disease/gene/pathway target, runs a
13-agent literature pipeline to build a mechanistic causal knowledge graph, generates and
gates novel hypotheses against the global literature, and exposes all of this through a UI
with an autonomy control and a reliability (eval flywheel) dashboard.

This repo is built in sequential phases; see `vertical_agent_build_prompt.md`-derived phase
history in `docs/architecture.md` (added in Phase 6) and commit history (one commit per
phase Definition-of-Done).

## Repo layout

```
/backend        FastAPI (Python) — agent orchestration, all pipeline logic
/frontend       React + TypeScript (Vite) — UI
/agents         AGENTS.md context files, one directory per agent (Phase 1)
/skills         SKILL.md reusable capability modules (Phase 1B)
/data/sessions  existing + future session JSON outputs, one folder per session
/data/graphs    per-disease knowledge_graph.json files
/eval           flywheel judge scripts + historical trace scoring (Phase 4)
/docs           architecture.md, demo script, failure-case log (Phase 6)

# Legacy pipeline output, pre-existing, never overwritten by this app:
/graph          original ad-hoc pipeline graph outputs (asthma, IBD, sessions 1-4)
/reports        original ad-hoc session markdown/JSON reports
/data/*.json    original ad-hoc raw pipeline data (Session 1/2 publications, etc.)
/scripts        original ad-hoc Python scripts that produced the above
```

`/data/graphs` and `/data/sessions` are **copies** of the legacy `/graph` and `/reports`
content, migrated into the new structure — see `/data/graphs/README.md` for one documented
data-lineage discrepancy found during migration.

## Running locally

### Docker (recommended)

```bash
cp .env.example .env   # optional: PUBMED_API_KEY / SEMANTIC_SCHOLAR_API_KEY / OPENALEX_MAILTO
                        # (no LLM API key needed -- see below)
docker compose up --build
```

- Backend: http://localhost:8000 (docs at `/docs`)
- Frontend: http://localhost:5173

### Without Docker

```bash
# backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# frontend (separate terminal)
cd frontend
npm install
npm run dev
```

## Architecture note: no LLM API key, ever

Every model call in this system runs through the developer's existing Claude subscription
via headless Claude Code CLI (`claude -p`) subprocess invocations from the backend -- there
is no `ANTHROPIC_API_KEY` anywhere in this codebase and the backend never calls an LLM API
directly. See `docs/architecture.md` (Phase 6) for the full rationale and verified
constraints (subscription auth, required `--permission-mode`/`--allowedTools` flags,
five-hour rate-limit window).

Each pipeline agent (`/agents/agentNN_<name>/AGENTS.md`) and Skill (`/skills/<name>/SKILL.md`)
is the canonical, human-edited source of truth. Running

```bash
python3 backend/generate_native_agents.py
```

regenerates the native Claude Code registrations (`.claude/agents/*.md`,
`.claude/skills/*/SKILL.md`) from them -- run this after editing any AGENTS.md or SKILL.md
file.

## Literature & novelty data sources: free-only

`pubmed-literature-search` (used by Agent 2, and independently by Agent 10/Agent 12) is the
canonical source of every external-search endpoint used in this system: PubMed E-utilities
(primary corpus), Semantic Scholar Graph API and OpenAlex API (independent structured
cross-checks for novelty verification). All three are free with no paid tier, ever.
**Google Scholar is never used** in any form (no official API, ToS prohibits scraping,
results aren't structured enough to log) -- see the skill file for the full rationale and a
documented real gap this fixes (Session 003's single-source zero-hit novelty calls).

## Pipeline agents (13 + orchestrator)

`Agent 1` (Baseline Canonical Knowledge) runs first, before any literature retrieval, and
pulls curated mechanistic facts from structured canonical databases (Reactome/KEGG/UniProt/
MyDisease.info) via the `canonical-baseline-lookup` skill, so that
downstream agents (especially Agent 10/Novelty Verification) don't have to re-discover
already-established science via a live literature search on every run. Its output
(`canonical_baseline.json`, `provenance_type: "canonical_db"`) is kept structurally distinct
from PMID-sourced content everywhere downstream (graph, UI, Agent 10's classification).
Agents 2-13 are the original literature -> graph -> hypothesis -> peer-review -> experiment
pipeline. `agent00_orchestrator` (unnumbered in the pipeline sequence) dispatches all 13 via
the CLI's subagent-dispatch tool and is not itself one of the numbered pipeline steps. (This
project's docs originally assumed that tool is named "Task" -- a live stream-json capture in
Phase 2 showed the currently-installed Claude Code CLI actually names it "Agent"; the backend
recognizes both names since "Task" is still a separately-listed CLI capability.)

## Status

Phase 0 (project scaffold): complete.
Phase 1 (context engineering layer): complete -- 13 agent AGENTS.md files + orchestrator
(Agent 0), native subagent generation, and a live test proving Agent 10 (Novelty
Verification) alone reproduces the real Session 002 H1 (RESTATED)/H2 (Established)
classifications.
Phase 1B (custom Skills layer): complete -- all 6 SKILL.md files
(`pubmed-literature-search`, `novelty-verification-protocol`, `contradiction-detection`,
`graph-export-visualization`, `cross-disease-motif-analysis`, `canonical-baseline-lookup`) +
`skills_manifest.json`, the orchestrator's AGENTS.md wired to consult the manifest and load
skills before each relevant pipeline step, and two live tests proving real runtime behavior
(not unused documentation): Agent 10 spontaneously invokes the `Skill` tool for
`novelty-verification-protocol` with no explicit instruction to do so, and Agent 1
spontaneously invokes the `Skill` tool for `canonical-baseline-lookup` and then calls
`WebFetch` against a real Reactome/KEGG/UniProt/MyDisease.info endpoint.

Phase 2 (pipeline orchestration): complete -- `backend/app/db.py` (SQLite run/event
persistence), `backend/app/orchestrator.py` (`StreamTranslator`: raw claude stream-json ->
UI progress events; `RunManager`: background run lifecycle + SSE fan-out), and
`backend/app/main.py` endpoints (`POST /api/pipeline/run`, `GET .../status`, `GET .../runs`,
`GET .../stream`). Per an explicit scope-trim request, the mocked-CLI test surface is one
orchestrator integration suite (`test_orchestrator.py`, 20 tests, zero live cost) rather than
one file per agent; live-model coverage is deliberately narrow and targeted at the two
safety-critical agents:
- Agent 10 (Novelty Verification) -- `test_agent10_novelty.py` (Phase 1): reproduces real
  historical H1 (RESTATED) / H2 (Established) classifications.
- Agent 9 (Contradiction & Gap Detection) -- `test_agent09_contradiction.py`: a genuine,
  reproducible (3/3 live runs) finding, kept as a documented `xfail` rather than hidden or
  loosened -- the agent reliably finds the well-known historical Batf3 contradiction but
  misses a second, less-familiar one in the same small fixture, even after two independent
  prompt-strengthening passes. This is the strongest concrete argument in this codebase for
  Phase 3's human sign-off and Phase 4's independent LLM-judge re-scoring as real safety nets,
  not formalities.
- One live orchestrator smoke test (`test_orchestrator_live_smoke.py`) exercising a real
  (cheap) `Skill` load + subagent dispatch end-to-end -- this is what caught the "Agent" vs
  "Task" tool-name bug above, plus two more real bugs fixed in the same pass: duplicate
  "unknown_skill"/"unknown_agent" junk events from `--include-partial-messages`' two-phase
  tool_use streaming, and a duplicate-terminal-event race where a second, empty-reason
  `orchestrator_failed` wrapper could clobber a real error message in both the DB and the SSE
  feed (caught for real during the dev-loop full-pipeline run below, which hit an actual
  Claude subscription rate limit mid-run).
- A real (not mocked) full 13-agent pipeline run was launched against a narrow, cheap
  dev-loop target (psoriasis + IL23A, Agent 2's PubMed retmax overridden to 25/year-band for
  this run only via `dev_pubmed_retmax`) to validate the orchestration chain end-to-end before
  any demo-quality run. Agent 1 completed a real 28-tool-call canonical-baseline lookup before
  the run hit the subscription's five-hour rate limit; to be retried once quota resets.

Phase 3 (autonomy control -- environment only, per an explicit "build the environment now,
live CLI tests later" request; zero live `claude` calls in this phase's own test suite):
- `runs.session_id` (`backend/app/db.py`): generated up front (`uuid4()`, not parsed back out
  of the first stream event) and persisted at run creation, so a run that pauses before its
  very first event still has a resumable session on file.
- `backend/app/claude_cli.py`: `_build_command` now only passes `--no-session-persistence` for
  the never-resumed single-shot agent calls; the orchestrator instead gets `--session-id
  <id>` on first launch and `--resume <id>` on resume, per `claude --help`'s documented
  flags -- this specific flag combination has NOT yet been exercised against the real CLI.
- Exact machine-parseable pause protocol formalized in `agents/agent00_orchestrator/AGENTS.md`:
  the orchestrator ends its turn with a first line of exactly
  `PAUSED_FOR_APPROVAL: <agent_name> — <reason>` at each of its `autonomy_level`'s pause
  points (every agent for `autocomplete`; before Agent 10's classification and before Agent 13
  for `supervised`; never for `let_it_rip`). `StreamTranslator` in `orchestrator.py` parses this
  exact marker into a `run_paused` UI event (kept distinct from `run_completed`, which the raw
  CLI `result` event otherwise looks identical to).
- `RunManager.resume_run()`: validates the run is actually `paused`, records the human's
  approve/reject/edit decision + optional note to the new `get_human_interventions` audit-trail
  table, and relaunches the SAME claude session (`resume=True`) with the decision as the next
  prompt. New endpoint `POST /api/pipeline/{run_id}/decision` (404 unknown run, 422 invalid
  decision value, 409 if the run isn't currently paused). `GET /api/pipeline/{run_id}/status`
  now also returns the full `interventions` audit trail for that run.
- Test coverage (all mocked, zero live cost): 11 new cases across `test_orchestrator.py`
  (pause-marker translation, session_id plumbing, full pause->resume->complete lifecycle
  against a fake two-stage claude_cli, resume validation errors) and a new `test_main_api.py`
  (4 cases, real FastAPI `TestClient` + mocked `claude_cli`, exercising the actual HTTP
  `/decision` endpoint end-to-end including its error responses).
- Deliberately NOT done in this pass (left for the "live CLI tests later" follow-up): no live
  run has actually exercised `--session-id`/`--resume` against the real `claude` binary yet, so
  the flag combination is unverified beyond `claude --help`'s documented behavior. No frontend
  UI for the autonomy slider or pause/approve controls -- that's Phase 5's job per this
  project's phase breakdown.

Phase 4 (eval flywheel -- built per the same "no live Claude calls unless explicitly requested"
constraint as Phase 3; the historical half is real data, the live-judge half is environment-only):
- **Historical backfill (`backend/app/eval.py`'s `backfill_historical_sessions`)**: pure,
  deterministic, zero-cost Python that parses the REAL, already-committed Session 001-003 files
  (`data/graphs/asthma/novelty_audit.json`, `reports/session_002_report.json`,
  `reports/session_003_report.json`) -- nothing here is synthesized, per the project's original
  constraint that Phase 4 depends on these three sessions being real historical data. One
  hardcoded scorer function per session (not a generic schema-sniffing parser: each historical
  session's file format genuinely differs, and a "clever" generic parser risks silently
  mis-extracting ground truth it was never shown). Actually run against the live DB (not just
  tested) -- see `eval/historical_backfill.json` for the real output:
  - H1/H2 (Session 001, the founding failure case from `immunology_pipeline.md`'s preamble) ->
    `confirmed_false_positive_historical`, ground truth RESTATED / "A -- Established consensus"
    respectively (from the real Session 002 re-audit).
  - H-S002-01 (Session 002) -> `correctly_rejected` (real 3-reviewer REJECT consensus).
  - H-D001 / H-C002 (Session 003) -> `accepted_pending_validation` -- deliberately NOT scored
    as correct/incorrect, since no wet-lab result exists anywhere in this repo; fabricating one
    would violate the same "never synthesize" constraint.
  - Session 004 (hardening pass) excluded, per `sessions_manifest.json`'s own
    `include_in_eval_flywheel: false` and an earlier explicit project decision.
- **Dashboard metrics (`compute_dashboard_metrics`)**: a real computed fact, not an assertion --
  both known historical false positives have a ground truth that is non-D/E under the CURRENT
  Agent 9/10 rule (only D/E may reach hypothesis generation), so `historical_gate_retroactive_
  catch_rate` correctly comes out to `1.0`: the mandatory novelty gate this project exists to
  enforce would have caught 100% of its own founding failure case, retroactively.
- **`agent14_eval_judge`** (`agents/agent14_eval_judge/AGENTS.md`, registered in
  `agent_registry.py` but deliberately excluded from `AGENT_ORDER`): an independent, blind
  post-hoc auditor for FUTURE live runs, institutionalizing the same external-audit principle
  that caught H1/H2 in the first place. `eval.py`'s `build_judge_prompt` withholds the
  pipeline's own classification label so `agrees_with_pipeline` is a real disagreement signal,
  not an anchored rubber stamp. Read-only tool grant (no `Write`) -- a verdict can never modify
  a pipeline session file or the knowledge graph itself.
- New endpoints: `POST /api/eval/backfill` (recompute, idempotent, zero cost), `GET
  /api/eval/dashboard`, `GET /api/eval/scores` (filterable by `subject_type`/`session_id`), and
  `POST /api/eval/judge/{run_id}` (dispatches `agent14_eval_judge` for one hypothesis -- a REAL,
  subscription-billed call; 404 unknown run, 409 if the run isn't `completed` yet).
- Test coverage (all mocked or against real static files, zero live `claude` cost): 18 cases in
  `test_eval_backfill.py` (real-file parsing correctness, dashboard math, agent shape, a mocked
  `run_live_judge` round-trip) + 7 cases in `test_eval_api.py` (the four new HTTP endpoints,
  including the mocked live-judge dispatch).
- Deliberately NOT done in this pass: `run_live_judge` has never been exercised against the real
  `claude` CLI (same "environment now, live tests later" pattern as Phase 3) -- there is also no
  completed live 13-agent run yet to judge, since Phase 2's dev-loop run hit a subscription rate
  limit mid-Agent-1. No dashboard UI -- Phase 5's job.

Phase 5 (UI): the real `/frontend` (React + TypeScript + Vite, scaffolded in Phase 0) now has
four working views wired to every real backend endpoint above -- nothing here is a mock or a
Phase 0-style stub anymore:
- **Launch & Runs** (`/`) -- start a real pipeline run (disease/gene, autonomy-level radio group,
  the same `dev_pubmed_retmax` cost knob as the backend), plus a polling table of all runs
  (`GET /api/pipeline/runs`).
- **Run detail** (`/runs/:runId`) -- subscribes to the real SSE stream
  (`src/api/sse.ts`'s `subscribeToRun`, one `addEventListener` per named event type, since the
  backend names each SSE event after its own `type` field rather than sending anonymous
  `message` events) and renders a live timeline of `skill_loaded`/`agent_started`/
  `agent_completed`/`run_paused`/`run_completed`/`run_failed`. When a run is `paused`, an
  approve/reject/edit panel posts straight to `POST /api/pipeline/{run_id}/decision`, and the
  full `human_interventions` audit trail renders once populated.
- **Graph Explorer** (`/graphs`) -- `react-cytoscapejs` rendering of a new backend endpoint,
  `GET /api/graphs/{disease_slug}` (`backend/app/graphs.py`), built specifically for this page:
  it strips the on-disk `knowledge_graph.json`'s full per-node/edge PMID lists (what makes the
  real asthma graph ~1.1MB for 838 nodes / 1143 edges) down to a `pmid_count` + a small citable
  sample (~392KB stripped) -- a rendering client needs the count for visual weight, not the
  whole list every load. Click any node/edge for its type/relation/confidence and PubMed-linked
  sample citations.
- **Reliability Dashboard** (`/eval`) -- renders the real Phase 4 backfill
  (`historical_gate_retroactive_catch_rate`, outcome breakdown, the actual scored-hypothesis
  table with real reasoning text) plus a "Recompute historical backfill" button
  (`POST /api/eval/backfill` -- pure/zero-cost, per Phase 4).
- Test coverage: 7 new mocked/real-file backend tests (`test_graphs_api.py`, same
  "real files, no synthesized content" pattern as `test_eval_backfill.py`). Frontend
  verification is `tsc -b` (clean), `vite build` (clean, no runtime dependency errors), `oxlint`
  (clean), and a live smoke check of both dev servers together (backend on :8000, frontend on
  :5173, CORS confirmed, every page module transforms without error) -- no frontend unit-test
  framework was added, consistent with this project's "important technical checks, not
  excessive test scope" standing constraint; there is no headless-browser tool available in this
  environment to capture an actual rendered screenshot as further evidence.
- Deliberately NOT done in this pass: no run has actually reached `paused`/`completed` against
  the real UI yet (no completed live 13-agent run exists on disk to click through), and the
  live-judge trigger button/UI for `POST /api/eval/judge/{run_id}` was intentionally left out of
  the dashboard for now (it dispatches a real, subscription-billed Claude Code call, and this
  project's standing constraint is to never wire a real-cost action behind a casual UI click
  without it being explicitly requested first).

See TODOs / commit history for phase progress.
