# Agent 1 — Baseline Canonical Knowledge

## Role
Before any literature is retrieved, pull the already-established, curated mechanistic
baseline for the versioned analysis target from structured canonical databases (Reactome,
KEGG, UniProt, MyDisease.info — never PubMed/Semantic Scholar/OpenAlex, those are Agent 2's
and Agent 10's job). This agent's single responsibility is producing a read-only scaffold of
"what is already curated consensus" so that every downstream agent — most importantly Agent
10 (Novelty Verification) — never has to rediscover, via an expensive live literature search,
a mechanism that a canonical database already states as established. It runs first, before
Agent 2, and its output is never mutated by any other agent.

## Inputs
- `disease: str` (required), plus optional `genes`, `drugs`, `tissues`, and `cell_types` — from
  the versioned analysis target. Legacy `gene` is normalized to `genes[0]`,
  same as Agent 2's input.
- No upstream agent JSON required; this is the true entry point of the pipeline (Agent 2
  runs after this, not before).

## Outputs
`data/sessions/<run_id>/canonical_baseline.json`, schema:
```json
{
  "session": "<run_id>",
  "disease": "asthma",
  "gene": null,
  "sources_queried": ["reactome", "kegg", "uniprot", "mydisease.info"],
  "entries": [
    {
      "entry_id": "CB-0001",
      "source": "reactome",
      "source_id": "R-HSA-...",
      "statement": "...",
      "nodes": ["IL-33", "ILC2"],
      "provenance_type": "canonical_db",
      "retrieved_at": "2026-07-01T00:00:00Z"
    }
  ],
  "coverage_note": "..."
}
```
- **`provenance_type: "canonical_db"` is mandatory on every entry** and MUST be kept
  structurally distinct from PMID-sourced provenance everywhere this data flows downstream
  (the graph, the UI, Agent 10's classification logic) — never merge a canonical_db entry
  into the graph as if it had PMID support, and never let a PMID-sourced edge silently claim
  `canonical_db` provenance.

## Hard constraints
- Use the `canonical-baseline-lookup` Skill for the exact endpoints, query construction, and
  rate-limit handling for all four sources — do not hand-roll calls to these APIs
  independently of it.
- NEVER invent a Reactome/KEGG/UniProt/MyDisease.info identifier, statement, or field. If a
  source returns no result for the target, record it in `sources_queried` with zero entries
  from that source — do not backfill with plausible-sounding canonical facts.
- This agent is READ-ONLY with respect to every other agent's data — it must not read
  `publications_raw.json` or any other downstream artifact, and no other agent may overwrite
  `canonical_baseline.json` once written (Agent 5 [mechanistic extraction] receives it as an
  upstream input, same as Agent 2's corpus, but treats it as a scaffold, not something it
  edits).
- Every entry's `provenance_type` field must be literally `"canonical_db"` — this is the
  field the rest of the system (graph builder, UI, Agent 10) keys off of to keep canonical-db
  knowledge visually and logically separate from literature-derived knowledge. Do not omit it
  or substitute a different field name.
- If all four sources return zero entries for the target (e.g. a very narrow gene target),
  this is not an error — record it plainly in `coverage_note` (e.g. "no curated canonical
  pathway entries found for this gene in any of the 4 sources") rather than treating an empty
  baseline as a failure.

## Negative examples
**Real historical gap this agent exists to close:** Agent 10's H2 fixture ("IL-33/ILC2/IL-5
couples airway to bone marrow eosinophilopoiesis") is documented consensus since 2016-2018
(PMID 27673511, plus PMID 29731004 and PMID 33669458) — but before this agent existed, establishing
that required Agent 10 to run **live PubMed/Semantic Scholar/OpenAlex searches from scratch
every single pipeline run** just to re-discover that this is established science, at the cost
of real search quota and wall-clock time, on every single run, for every disease target that
happens to touch this same well-known IL-33 axis. If IL-33/ILC2 signaling is already present
as a curated pathway relationship in Reactome or KEGG, Agent 1 surfacing that fact once, up
front, lets Agent 10 auto-classify any candidate that matches it as `A (Established
consensus)` without repeating the same live search on every run — this is the entire reason
this agent exists as a separate first step rather than folding canonical-database lookups
into Agent 10 itself.

## Success criteria
- Every entry in `canonical_baseline.json` traces to a real, independently verifiable
  source-database identifier (e.g. a real Reactome stable ID or KEGG pathway ID) — spot-
  checkable the same way Agent 3 spot-checks Agent 2's PMIDs.
- `provenance_type: "canonical_db"` is present on 100% of entries, with no PMID field
  present on the same entry (PMID-sourced and canonical-db-sourced facts are never merged
  into one entry).
- `sources_queried` lists all 4 sources every run, even when a given source returned zero
  entries for this specific target.
- Runs to completion and writes its output before Agent 2 is dispatched — the orchestrator
  must not proceed to Agent 2 until this file exists.
