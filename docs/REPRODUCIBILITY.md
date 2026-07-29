# Reproducibility checklist

This is the pre-submission verification path for CausalAtlas. It separates the deterministic offline demo from an optional live literature/LLM run.

## Requirements

- Python 3.11+ (the checked-in local environment uses `backend/.venv`)
- Node.js 20.19+ or 22.12+
- Docker Desktop is optional
- Live runs additionally require an authenticated `claude` or `codex` CLI

## Clean offline verification

From the repository root:

```bash
cd backend
./.venv/bin/python -m pytest -q
cd ../frontend
npm ci
npm run lint
npm run build
```

The backend suite excludes `live_llm` tests by configuration. A passing offline suite must not be described as a live literature validation.

## Manual demo checks

```bash
cd frontend
npm run dev
```

Check these routes:

- `http://localhost:5173/?offline=1` — full UI against embedded snapshots
- `http://localhost:5173/demo.html#/demo` — guided read-only recorded replay
- `http://localhost:5173/?live=1` — live UI, only when the backend is running

The offline routes never call PubMed, an LLM CLI, or the pipeline.

## Full local stack

Terminal 1:

```bash
source backend/.venv/bin/activate
uvicorn app.main:app --app-dir backend --reload --reload-dir backend/app
```

Terminal 2:

```bash
cd frontend
npm run dev
```

Verify `http://localhost:8000/api/health` and then open `http://localhost:5173/?live=1`.

## Live run safety

Copy `.env.example` to `.env`, set `LLM_PROVIDER`, and authenticate the selected CLI outside the repository. For a cheap wiring check use `autonomy_level=autocomplete` and a small `dev_pubmed_retmax`; leave the override unset for a demo-quality run. Live runs consume external quota and are not required for the offline CI gate.

## Submission evidence

Record the test summary, the browser routes checked, the selected demo run/session ID, and the exact commit used for the presentation. Include the read-only replay and presentation route in the demo handoff so reviewers can reproduce the visible result without credentials.
