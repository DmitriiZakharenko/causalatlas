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
cp .env.example .env   # fill in PUBMED_API_KEY / ANTHROPIC_API_KEY
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

## Status

Phase 0 (project scaffold) complete. See TODOs / commit history for phase progress.
