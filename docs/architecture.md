# Runtime architecture

The project has four explicit layers:

1. **Context** — the root `AGENTS.md`, per-agent contracts in `agents/`, and reusable procedures in `skills/`.
2. **Execution** — FastAPI, the provider adapters, sequential orchestration, JSONL event translation, SQLite persistence, and SSE streaming in `backend/app/`.
3. **Scientific state** — run-scoped artifacts/checkpoints under `data/sessions/` and cumulative disease graphs under `data/graphs/`.
4. **Presentation** — React live/offline views, graph/evidence inspection, autonomy controls, eval dashboard, recorded replay, and the presentation route in `frontend/`.

The Claude provider uses the native CLI orchestration path. The Codex provider uses sequential `codex exec --json` calls for language-heavy stages and deterministic Python for graph stages. Both providers emit the same UI event vocabulary. This is an explicit implementation tradeoff, not native-subagent parity.

The safety boundary is the novelty gate: canonical baseline lookup and a structural restatement test precede independent external searches; A/B/C outcomes are routed away from hypothesis generation, and only D/E candidates can continue to peer review and experiment design. A completed pipeline is not automatically a valid hypothesis.

See `docs/REPRODUCIBILITY.md` for the exact offline and live verification commands.
