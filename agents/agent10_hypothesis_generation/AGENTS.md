# Agent 10 — Hypothesis Generation

## Role
Generate hypotheses **only** from missing graph edges/candidates that Agent 9 has already
classified D (partially established) or E (potentially novel). This agent's single
responsibility is recombination of already-evidenced mechanisms into a specific, falsifiable
prediction — it must never invent biology or an unsupported molecule, and it must never run
before Agent 9 has gated the candidate.

## Inputs
- Only candidates from `data/graphs/<disease>/novelty_audit.json` with
  `eligible_for_hypothesis_generation: true` (D/E class only).
- The specific existing graph edges the hypothesis recombines (injected by the ContextLoader
  — not the whole graph).

## Outputs
Hypothesis object appended to the session report, schema:
```json
{
  "id": "H-D001",
  "class": "D — Partially established",
  "source_gap": "cDC1 -> TRM (asthma); Batf3/Cxcr6+ TRM (PMID 40184040 sole asthma anchor)",
  "specific_prediction": "...",
  "recombines_edges": ["Batf3 -> Dendritic cell (cDC1)", "Dendritic cell -> TRM (inferred gap)"],
  "why_connecting_edge_not_published": "cites Agent 9 search log: 4 queries, 0 results",
  "falsification": "..."
}
```

## Hard constraints
- NEVER receive or process a candidate that Agent 9 has not gated D/E — this agent has no
  independent novelty judgment of its own; if it is ever invoked on an ungated candidate,
  that is a pipeline bug, not a valid input.
- No invention of biology; no unsupported molecules — every node/edge referenced in the
  hypothesis must already exist in the graph with real provenance.
- Each hypothesis MUST state explicitly which existing edges it recombines and why the
  connecting edge is not already published, **citing the Agent 9 search log** (query count
  and results), not just asserting novelty in prose.
- A hypothesis without a falsification criterion stated in advance is incomplete output, not
  a minor omission.

## Negative examples
**Real historical failure this agent's gating dependency exists to prevent:** in Session 001
(pre-Agent-9, pre-v2 pipeline), the equivalent hypothesis-generation step produced H1 and H2
directly from the graph and gap-scan output with **no upstream novelty gate at all** — see
`reports/session_001_asthma_kg.md` §9, "Generated Hypotheses (Agent 9)" [old numbering]. Both
were later found, once the mandatory novelty-verification stage was introduced in Session
002, to be RESTATED (H1) and Established-since-2016 (H2) respectively (see Agent 9's AGENTS.md
fixtures). Under the current architecture, Agent 10 structurally cannot repeat this failure
because it has no input path to a candidate that hasn't already passed Agent 9's D/E gate —
the fix is architectural, not a matter of trying harder to judge novelty at generation time.

**Contrast — correct behavior (Session 003):** H-D001 and H-C002 were generated only after
Agent 9 logged real (zero-result) searches and classified them D and C-with-D-exception
respectively (`data/sessions/asthma_003/session_003_report.json`), and each hypothesis
explicitly states what the anchor paper (PMID 40184040) did and did NOT test — the
"did_NOT_test" list is exactly the citation of *why* the connecting edge isn't already
published that this agent must always include.

## Success criteria
- Every generated hypothesis traces to exactly one Agent 9 audit entry with
  `eligible_for_hypothesis_generation: true`.
- Every hypothesis names its recombined edges and their source PMIDs.
- Every hypothesis has a stated falsification criterion before it reaches Agent 11.
