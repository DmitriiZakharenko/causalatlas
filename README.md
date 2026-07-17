<div align="center">

# CausalAtlas

### Auditable mechanistic reasoning for biomedical discovery

Turn a disease + target question into a traceable path from canonical biology and literature evidence to a causal graph, a novelty decision, and a falsifiable experiment.

<p>
  <a href="#quickstart"><img src="https://img.shields.io/badge/quickstart-2_minutes-1ca78a?style=flat-square" alt="Quickstart" /></a>
  <a href="#offline-demo"><img src="https://img.shields.io/badge/demo-zero_backend-4c6fff?style=flat-square" alt="Offline demo" /></a>
  <a href="#security"><img src="https://img.shields.io/badge/security-no_committed_secrets-9254c7?style=flat-square" alt="Security" /></a>
  <img src="https://img.shields.io/badge/status-research_prototype-c47718?style=flat-square" alt="Research prototype" />
</p>

<img src="docs/causalatlas-pipeline.svg" alt="CausalAtlas pipeline: evidence, causal graph, novelty gate, peer review and experiment" width="100%" />

<p><em>Research software, not medical advice. Outputs are hypotheses for expert review.</em></p>

</div>

## The idea

Language models are excellent at producing plausible biological stories. Plausibility is not novelty, causality, or evidence.

CausalAtlas separates those questions into inspectable stages:

| Stage | What it protects against | Output |
| --- | --- | --- |
| Canonical baseline | Rediscovering established biology | Curated pathway facts |
| Literature + verification | Weak or misidentified sources | Verified evidence corpus |
| Causal graph | Untraceable narrative claims | Provenance-backed edges |
| Novelty gate | False novelty | A–E classification |
| Peer review + experiment | Attractive but unfalsifiable ideas | Testable validation plan |

## What you get

- **Live analysis UI** — launch runs, stream progress, inspect checkpoints and approve pause points.
- **Causal graph explorer** — explore nodes, edges, loops, gaps and contradictions by disease.
- **Evidence dashboard** — follow a claim from source publication to graph edge and hypothesis.
- **Evaluation flywheel** — replay historical cases and compare pipeline decisions with independent review.
- **Offline presentation mode** — inspect the product without Docker, backend, model login or API keys.

## Quickstart

### Full stack with Docker

Requirements: Docker Desktop and Docker Compose.

```bash
git clone <your-repository-url>
cd causalatlas
cp .env.example .env
docker compose up --build
```

Open [localhost:5173](http://localhost:5173). API docs are available at [localhost:8000/docs](http://localhost:8000/docs).

### Local development

Requirements: Python 3.11+ and Node.js 20.19+ or 22.12+.

```bash
# terminal 1 — backend
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
uvicorn app.main:app --app-dir backend --reload

# terminal 2 — frontend
cd frontend
npm ci
npm run dev
```

The `.env.example` file documents optional literature rate-limit settings. Empty values are valid.

## Offline demo

No backend. No database. No model login. No API keys.

```bash
cd frontend
nvm use
npm ci
npm run build
npm run preview
```

Open the printed URL followed by [`/demo.html`](http://localhost:4173/demo.html). The replay is read-only, makes no network requests, and includes animated `Play replay` flow controls. It can be hosted as a static page on GitHub Pages.

## Architecture

```text
question: disease + target
          │
          ▼
canonical baseline → literature → verification → quality filter
          │                                      │
          └──────── causal graph ◄─ mechanism extraction
                              │
                              ▼
             novelty gate → hypothesis → review → experiment
```

| Directory | Responsibility |
| --- | --- |
| `backend/` | FastAPI, SQLite persistence, orchestration and graph/evidence endpoints |
| `frontend/` | React + TypeScript + Vite interface |
| `agents/` | Human-readable contracts for pipeline roles |
| `skills/` | Reusable retrieval, novelty, contradiction and graph procedures |
| `data/graphs/` | Disease-level graph artifacts |
| `data/sessions/` | Pipeline artifacts and checkpoints |
| `docs/` | Architecture, presentation notes and visual assets |
| `eval/` | Historical backfill and evaluation utilities |

## Configuration and security

Copy `.env.example` to `.env`. Never place credentials in Python, TypeScript, JSON, screenshots, issues or commits.

- `PUBMED_API_KEY` and `PUBMED_EMAIL` are optional.
- `SEMANTIC_SCHOLAR_API_KEY` is optional.
- `OPENALEX_MAILTO` is optional.
- `VITE_*` values are public browser configuration and must never contain secrets.

See [SECURITY.md](SECURITY.md) for reporting guidance. If a real credential was ever committed, revoke and rotate it; deleting the line is not enough because Git history retains it.

## Verification

```bash
cd frontend
npm run lint
npm run build

cd ../backend
pytest -q
```

For cheap wiring checks, use `autonomy_level=autocomplete` and a small `dev_pubmed_retmax`. Live model runs can consume subscription quota and should be started deliberately.

## Project status

CausalAtlas is an experimental research platform. It is intentionally transparent about uncertainty, failed checks and human approval points. Contributions that improve provenance, reproducibility, evaluation or safety are welcome.

## License and citation

Add the preferred license and citation metadata before making the repository public. Scientific artifacts retain source identifiers and should be cited according to their originating databases and publications.
