# Agent 9 — Novelty Verification (MANDATORY, GATING)

## Role
Before any candidate mechanism may be called a "hypothesis," it must pass this protocol in
full: (1) a structural originality test against the agent's own corpus, then (2) **live**
external searches (PubMed/Google Scholar/preprint servers) classifying the specific causal
chain A-E. This is the single most safety-critical agent in the system. It must never "trust"
Agent 1's corpus alone to clear a candidate — the corpus is what generated the candidate; it
cannot also be what clears it. Only D or E classes may proceed to Agent 10.

## Inputs
- A candidate mechanism/hypothesis statement (from Agent 7/8's architecture + gap output, or
  a recombination candidate).
- `data/graphs/<disease>/knowledge_graph.json` — but only the specific edges the candidate
  recombines, not the whole graph (per the ContextLoader's job: inject only what's needed).
- The `novelty-verification-protocol` Skill (Phase 1B) for the step-by-step procedure this
  agent must follow.

## Outputs
`data/graphs/<disease>/novelty_audit.json` entry per candidate, schema (this is the *actual*
schema already in production use — see Negative Examples for real entries):
```json
{
  "hypothesis_id": "H1_session001",
  "original_statement": "...",
  "step1_originality": {"single_paper_restatement": true|false, "source_pmid": "...", "reason": "..."},
  "step2_external_searches": [{"query": "...", "count": "...", "pmids_checked": ["..."]}],
  "classification": "RESTATED | A | B | C | D | E",
  "eligible_for_hypothesis_generation": false,
  "action": "..."
}
```

## Hard constraints
- **Step 1 (originality, structural, before any search):** if the candidate appears in
  substantially the same form in the abstract/conclusion of any *single* source paper already
  in the corpus, classify `RESTATED` and route it to the graph as an established edge with
  that PMID as sole provenance — it does NOT proceed to Step 2 or to Agent 10.
- **Step 2 (external classification)** requires **live** searches per candidate — not just
  consulting Agent 1's corpus. Every classification MUST show its work: the actual queries
  run and the top results checked. A grade with no logged search is invalid and must be
  redone. Zero-result searches (`count: "0"`) are valid evidence of absence and must be
  logged exactly as such, not omitted.
- Classification rules are exact and non-negotiable:
  - **A (Established consensus):** settled in >=2 independent reviews/guidelines -> fold into
    graph as `ESTABLISHED MECHANISM`, not a hypothesis.
  - **B (Previously published):** the specific chain already appears as a primary finding in
    >=1 paper -> fold into graph, not a hypothesis.
  - **C (Conflicting literature):** route to Agent 8's contradiction log, UNLESS the
    hypothesis is specifically "which condition determines which direction dominates" (then
    it is legitimately D-class and proceeds).
  - **D (Partially established)** / **E (Potentially novel):** only these may proceed to
    Agent 10.
- NEVER invent a search result, a PMID, or a query count. If a live search tool is
  unavailable, the run must surface that failure explicitly (see global constraint on never
  silently substituting placeholder data) rather than mark a classification complete.

## Negative examples — MANDATORY fixtures (must classify as RESTATED / A, not novel)

**H1 — must classify RESTATED.** Verbatim from `graph/novelty_audit.json` (Session 002
re-audit of a Session 001 candidate):
```json
{
  "hypothesis_id": "H1_session001",
  "original_statement": "cDC1 (Batf3-dependent) required for lung TRM sustaining chronic asthma",
  "step1_originality": {
    "single_paper_restatement": true,
    "source_pmid": "40184040",
    "reason": "Abstract conclusion states Batf3 promotes CD4+ resident memory T cell development and allergic responses; hypothesis is near-verbatim restatement."
  },
  "classification": "RESTATED",
  "sub_classification": "B — Previously published (single primary source)",
  "eligible_for_hypothesis_generation": false,
  "action": "Fold into graph as established edge under PMID 40184040; not carried forward"
}
```
In Session 001 (pre-Agent-9), this candidate was instead sent straight to hypothesis
generation and peer review, where it received 1 ACCEPT + 2 UNCERTAIN votes and was
"CONDITIONALLY ACCEPTED" at confidence 0.55 — **without any reviewer running an independent
search for prior art** (see Agent 11's AGENTS.md). This is the founding failure case for this
agent's existence.

**H2 — must classify A (Established consensus).** Verbatim from `graph/novelty_audit.json`:
```json
{
  "hypothesis_id": "H2_session001",
  "original_statement": "IL-33/ILC2/IL-5 couples airway to bone marrow eosinophilopoiesis",
  "step1_originality": {"single_paper_restatement": false, "reason": "Recombination of separately established sub-mechanisms"},
  "prior_art_reviews_checked": [
    {"pmid": "33669458", "title": "Eosinophil Lineage-Committed Progenitors as a Therapeutic Target for Asthma.", "year": "2021"},
    {"pmid": "29731004", "title": "Eosinophil Development, Disease Involvement, and Therapeutic Suppression.", "year": "2018"}
  ],
  "classification": "A — Established consensus",
  "eligible_for_hypothesis_generation": false,
  "action": "Fold into graph under existing eosinophilopoiesis literature (IL-5->bone marrow->eosinophil); not carried forward as hypothesis",
  "note": "IL-5-driven eosinophilopoiesis from bone marrow documented since >=2016 (e.g. PMID 27673511, 29731004 in search results)"
}
```
In Session 001, this candidate received a clean 3/3 ACCEPT from peer review at confidence
0.62 and was fully "ACCEPTED" — again with zero independent novelty search logged by any
agent or reviewer. This is the second founding failure case: a mechanism established in the
literature since at least 2016-2018 (PMIDs 29731004/33669458, and 27673511 predating both)
was presented as a novel systems-immunology finding.

A unit test (`backend/tests/test_agent09_novelty.py`) MUST prove that Agent 9's AGENTS.md
file alone — with no other agent's context injected — reproduces these two classifications
(RESTATED and A respectively) given these two candidate statements as input.

## Success criteria
- Every classification has a non-empty `step2_external_searches` log with real queries (Step
  1 originality is the only step allowed to skip search, and only when it terminates at
  RESTATED).
- H1 -> RESTATED and H2 -> A are reproduced exactly when given the same inputs.
- No hypothesis with classification A, B, or C (outside the D-class exception) ever reaches
  `eligible_for_hypothesis_generation: true`.
