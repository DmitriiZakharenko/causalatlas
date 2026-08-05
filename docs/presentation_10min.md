# LoopFinder: From Literature to Testable Mechanistic Hypotheses

10-minute presentation script and slide plan.

## Slide 1 — The problem: plausible is not proven

**On slide**

> Biomedical literature is too large for a single researcher to search exhaustively.
>
> But the bigger risk is not missing a paper.
>
> It is presenting an already-known mechanism as a new discovery.

**Speaker script — 0:00–0:45**

"Let me start with the failure mode we wanted to eliminate. A biological story can sound completely new while every individual step is already established. A language model is very good at connecting plausible facts, but plausibility is not novelty, and plausibility is not causality. LoopFinder is designed around that distinction. It takes a disease and a gene, builds an evidence-backed mechanistic graph, and only then decides whether a candidate deserves to be called a hypothesis."

**Technical note**

- The system does not ask one model for a final answer.
- It separates retrieval, verification, graph construction, novelty classification, peer review, and experiment design.

## Slide 2 — The product in one sentence

**On slide**

> Input: a versioned target: disease, gene, drug, tissue, or cell type
>
> Output: evidence graph + novelty audit + falsifiable experiment plan

```text
IBD + NOD2
    -> literature corpus
    -> verified evidence
    -> causal graph
    -> novelty gate
    -> H-D001
    -> E1-1 / E1-2
```

**Speaker script — 0:45–1:25**

"The input is deliberately small: a disease and a target gene. The output is not a paragraph. It is a chain of auditable artifacts: verified papers, directed graph edges, a novelty classification, a hypothesis with a specific prediction and falsification criterion, and finally an experiment design. Every transition has a persisted file and a visible UI event."

## Slide 3 — The 13-agent architecture

**On slide**

```text
Orchestrator
    |
    v
01 Canonical baseline -> 02 Literature -> 03 Verification -> 04 Quality
                                                               |
                                                               v
05 Mechanistic extraction -> 06 Graph -> 07 Loops -> 08 Topology -> 09 Contradictions
                                                               |
                                                               v
10 Novelty gate -> 11 Hypothesis generation -> 12 Peer review -> 13 Experiment design
```

**Speaker script — 1:25–2:20**

"The pipeline is sequential because the dependencies are real. Agent 1 establishes the canonical baseline from Reactome, KEGG, UniProt, and MyDisease.info. Agent 2 builds a literature corpus using mechanism-specific searches. Agents 3 through 5 verify, rank, and extract causal statements. Agents 6 through 9 turn those statements into a graph and stress-test its topology and contradictions. Agent 10 is the novelty gate. Only after that can Agent 11 generate hypotheses, Agent 12 try to falsify them, and Agent 13 design an experiment."

"This is also why a failure at one stage should not be hidden by a plausible downstream answer. The UI separates pipeline completion from hypothesis readiness."

## Slide 4 — What is code and what is Markdown?

**On slide**

| Layer | Source of truth | Responsibility |
|---|---|---|
| Runtime | `backend/app/*.py` | subprocesses, orchestration, parsing, persistence, API |
| Agent contract | `agents/agentNN_*/AGENTS.md` | role, inputs, outputs, constraints, failure rules |
| Reusable skill | `skills/*/SKILL.md` | procedural method, search protocol, safety checks |
| State | `data/sessions/<run_id>/*.json` | durable hand-offs and checkpoints |
| Interface | `frontend/src/` | live progress, graphs, evidence, hypotheses, experiments |

**Speaker script — 2:20–3:15**

"A key design decision is that the biological and procedural instructions are not buried in Python. Python owns execution: it starts subprocesses, translates JSONL events, writes SQLite records, persists artifacts, and serves the API. Markdown owns context: each agent has an AGENTS.md contract, and reusable capabilities are SKILL.md modules."

"That separation matters. We can change the novelty protocol without rewriting the process manager. We can also inspect the exact instruction that governed an agent after the run. The Markdown files are not documentation next to the system; they are part of the runtime context engineering layer."

## Slide 5 — One agent in detail: Agent 10

**On slide**

```text
Candidate chain
      |
      v
0. Canonical baseline match?
      |
1. Single-paper restatement?
      |
2. Independent searches:
   PubMed + OpenAlex / Semantic Scholar
      |
      v
A / B / C / D / E / RESTATED
      |
      +--> only D/E may reach Agent 11
```

**Speaker script — 3:15–4:35**

"Agent 10 is the safety-critical example. Its job is not to invent a mechanism. Its job is to challenge one. It receives a candidate causal chain, the relevant graph edges, the canonical baseline, and the novelty-verification skill."

"First it checks whether the chain is already present in curated databases. That is class A. Next it checks whether the proposed claim is simply the conclusion of one source paper. That is RESTATED. If it survives those checks, it performs independent searches across at least two external sources, rather than trusting the corpus that generated the candidate. It assigns A through E: established, published, conflicting, partially established, or potentially novel. Only D and E are eligible for Agent 11."

"This gate is deliberately conservative. A zero-hit search is not automatically novelty. The query, source, result count, and evidence are persisted."

**Technical walkthrough**

- Contract: `agents/agent10_novelty_verification/AGENTS.md`
- Procedure: `skills/novelty-verification-protocol/SKILL.md`
- Search skill: `skills/pubmed-literature-search/SKILL.md`
- Runtime dispatch: `backend/app/codex_pipeline.py` or `backend/app/orchestrator.py`
- Output: `novelty_audit.json`

## Slide 6 — Concrete example: IBD + NOD2

**On slide**

> **H-D001 — D, Partially established**
>
> NOD2 risk variants may weaken muramyl-dipeptide-induced NOD2–GIV assembly and downstream cAMP production in intestinal epithelial cells, reducing mucosal barrier integrity. Restoring GIV/Gαi signaling should rescue the barrier phenotype.

**Speaker script — 4:35–5:45**

"Here is a concrete output from an IBD plus NOD2 run. The system did not claim that the entire mechanism was unknown. It identified a specific gap: NOD2 variants and the NOD2–GIV/cAMP axis are individually supported, but the variant-to-axis bridge in intestinal tissue is not established."

"The hypothesis is therefore narrow and testable. It predicts a measurable molecular event, a cAMP response, and a barrier phenotype. It also predicts rescue after restoring GIV/Gαi signaling. This is much stronger than saying 'NOD2 may be involved in inflammation.'"

## Slide 7 — From hypothesis to experiment

**On slide**

```text
E1-1: patient-derived and CRISPR-isogenic ileal organoid monolayers
      measure NOD2-GIV assembly, cAMP, TEER, FITC-dextran flux

E1-2: restore GIV/Gαi signaling or correct NOD2
      repeat stimulation and barrier assays

Falsification:
      no genotype difference, or no pathway-specific rescue
```

**Speaker script — 5:45–6:45**

"Agent 13 turns the surviving hypothesis into a validation plan. E1-1 compares patient-derived or CRISPR-isogenic intestinal monolayers after muramyl dipeptide stimulation. It measures NOD2–GIV assembly, cAMP, and barrier integrity through TEER and FITC-dextran flux. E1-2 is the rescue experiment: restore the GIV/Gαi arm or correct NOD2 and test whether the phenotype moves."

"The important part is the falsification criterion. If the variant and control cells behave the same, or if rescue does not restore the barrier phenotype, the hypothesis is rejected. The system is not rewarded for producing a positive story."

## Slide 8 — Codex backend and the multi-agent tradeoff

**On slide**

```text
FastAPI
  -> LLM_PROVIDER=codex
  -> codex exec --json -C <repo> \
       --dangerously-bypass-approvals-and-sandbox
  -> JSONL event translator
  -> SQLite + session artifacts + SSE
```

**Speaker script — 6:45–7:40**

"The project supports two subprocess backends. The original Claude CLI path preserves native Task and Skill orchestration. The Codex path uses JSONL subprocess execution and maps its events into the same UI event model. This lets the frontend remain backend-agnostic."

"There is one honest limitation: Codex does not provide Claude Code's native 13-subagent Task tool. The Codex runner therefore uses separate agent calls for language-heavy stages and deterministic Python for graph stages 6 through 9. That is a deliberate cost and reliability tradeoff, not hidden parity marketing."

**Technical details**

- `backend/app/codex_cli.py`: command construction and JSONL translation.
- `backend/app/llm_cli.py`: provider selection.
- `backend/app/codex_pipeline.py`: sequential Codex agent runner and deterministic stages.
- `backend/app/orchestrator.py`: run lifecycle, SSE, cancellation, event persistence.
- `data/sessions/<run_id>/checkpoints/`: resumable progress for bounded search agents.

## Slide 9 — Reliability is part of the product

**On slide**

> Every run leaves an audit trail.

```text
raw JSONL -> translated UI event -> SQLite event -> session artifact
```

**Speaker script — 7:40–8:35**

"The system is built for failure because external literature search and model subprocesses fail in ordinary ways. We persist raw outputs, checkpoints, verified papers, graph files, novelty audits, peer reviews, and experiment designs. Agent 2, Agent 10, and Agent 12 have query limits, publication limits, deadlines, and checkpoints."

"The interface distinguishes a completed pipeline from a ready hypothesis. A run can complete all thirteen stages and still have zero defensible hypotheses. That is not a UI bug; it is a scientifically meaningful outcome."

## Slide 10 — Closing: the design principle

**On slide**

> Do not ask an LLM for a discovery.
>
> Ask a sequence of agents to earn one.

**Speaker script — 8:35–10:00**

"LoopFinder is an attempt to turn open-ended scientific reasoning into an auditable workflow. The LLM contributes interpretation and search judgment, but the system constrains when a claim can move forward. Canonical knowledge prevents rediscovery. Independent novelty search prevents false novelty. Graph provenance keeps causal edges inspectable. Peer review and falsification protect against attractive stories."

"The output is not 'the model says this is true.' The output is a trace: these papers support these edges, this candidate survived this gate, these reviewers challenged it, and this experiment could prove it wrong. That is the standard we want for AI-assisted mechanistic discovery."

## Demo order during the talk

1. Open `/architecture` and show the 13-agent flow and Agent 10 detail.
2. Open `/evidence` and select `ibd_20260713T171442Z`.
3. Show **Generated hypothesis**: `H-D001`.
4. Show **Experiment design**: `E1-1` and `E1-2`.
5. Open `/graphs` and select the versioned IBD/NOD2 graph.
6. Return to the novelty table and explain why a `B` or `RESTATED` candidate is not promoted.

## Presenter cheat sheet: what to say if asked

### Are these real agents?

"Yes, in the runtime sense: each stage has a separate agent contract, receives explicit upstream artifacts, produces a persisted output, and emits a real dispatch/completion event. The Codex backend approximates native Claude subagent orchestration with sequential subprocess calls; the Claude backend uses the native CLI capabilities."

### Why not one large prompt?

"Because retrieval cannot independently validate its own novelty, and because a single answer hides provenance, failure boundaries, and contradictory evidence. Sequential stages make the claims inspectable."

### Why Markdown instead of only Python?

"The biological procedure changes more often than the runtime. AGENTS.md and SKILL.md make the procedure editable, reviewable, and reusable without changing orchestration code."

### What is deterministic?

"Persistence, event translation, budgets, checkpoints, graph transformations, and API behavior are code. The interpretation-heavy steps use the selected LLM backend. In the Codex runner, graph stages 6 through 9 are intentionally deterministic to reduce cost and variance."

### What is the main limitation?

"The evidence is only as good as the searchable and verified literature, and novelty is a classification under a documented search protocol, not a proof that no one has ever made the claim. The system exposes that uncertainty instead of hiding it."
