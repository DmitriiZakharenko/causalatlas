# LoopFinder

A full-stack vertical AI agent product: ingests a disease/gene/pathway target, runs a
12-agent literature pipeline to build a mechanistic causal knowledge graph, generates and
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

`pubmed-literature-search` (used by Agent 1, and independently by Agent 9/Agent 11) is the
canonical source of every external-search endpoint used in this system: PubMed E-utilities
(primary corpus), Semantic Scholar Graph API and OpenAlex API (independent structured
cross-checks for novelty verification). All three are free with no paid tier, ever.
**Google Scholar is never used** in any form (no official API, ToS prohibits scraping,
results aren't structured enough to log) -- see the skill file for the full rationale and a
documented real gap this fixes (Session 003's single-source zero-hit novelty calls).

## Status

Phase 0 (project scaffold): complete.
Phase 1 (context engineering layer): complete -- 12 agent AGENTS.md files + orchestrator
(Agent 0), native subagent generation, and a live test proving Agent 9 alone reproduces the
real Session 002 H1 (RESTATED)/H2 (Established) classifications.
Phase 1B (custom Skills layer): complete -- 5 SKILL.md files
(`pubmed-literature-search`, `novelty-verification-protocol`, `contradiction-detection`,
`graph-export-visualization`, `cross-disease-motif-analysis`) + `skills_manifest.json`, the
orchestrator's AGENTS.md wired to consult the manifest and load skills before each relevant
pipeline step, and a live test proving Agent 9 spontaneously invokes the `Skill` tool for
`novelty-verification-protocol` with no explicit instruction to do so -- real runtime
behavior, not unused documentation.
See TODOs / commit history for phase progress.
