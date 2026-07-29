# CausalAtlas — project context

## Mission

CausalAtlas is a research prototype for auditable biomedical mechanism discovery. It turns a disease/target question into a provenance-backed evidence graph, an independently checked novelty classification, a falsifiable hypothesis, and an experiment design.

## Non-negotiable constraints

- Treat the knowledge graph as a graph of published evidence, not as biological truth.
- Never invent papers, PMIDs, mechanisms, measurements, identifiers, or experimental results.
- Keep contradictory edges and their provenance; do not silently resolve conflicts.
- Do not call a mechanism novel without a documented independent search and an A–E classification. Only D/E candidates may proceed to hypothesis generation.
- Keep canonical database provenance distinct from PMID provenance.
- Preserve failed, paused, and partial runs as explicit states with their artifacts/checkpoints; never fill missing downstream output with plausible text.
- The product is research software, not medical advice or a clinical decision system.

## Context and execution layers

- `agents/*/AGENTS.md` defines each agent's role, inputs, outputs, constraints, and acceptance criteria.
- `skills/*/SKILL.md` defines reusable procedures and safety protocols.
- `backend/app/` owns execution, persistence, provider adapters, API, SSE, and deterministic graph stages.
- `frontend/` owns the live UI, offline snapshot UI, recorded replay, and presentation mode.
- `data/sessions/` contains run-scoped artifacts; `data/graphs/` contains disease-scoped exports; historical fixtures are read-only inputs to eval.

## Reproducibility contract

Use the commands in `docs/REPRODUCIBILITY.md`. Offline verification must pass before a submission: backend tests, frontend lint/typecheck/build, API health, and the read-only replay. Live LLM runs are opt-in and must use an authenticated local CLI; credentials never enter the repository or browser bundle.

## Change discipline

Prefer additive, traceable changes. Do not overwrite historical scientific artifacts in place. When changing a contract, skill, schema, or runtime behavior, update its tests and the relevant presentation/demo explanation in the same change.
