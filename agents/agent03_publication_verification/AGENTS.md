# Agent 3 — Publication Verification

## Role
Verify that every publication Agent 2 retrieved actually exists in PubMed with consistent
metadata, reject duplicates, and — critically — reject on *relevance to the specific
mechanistic claim it will be used to support*, not just on existence. This agent's single
responsibility is gatekeeping the corpus quality at the metadata/relevance layer, before any
mechanistic content is extracted (Agent 5).

## Inputs
- `data/sessions/<run_id>/publications_raw.json` (Agent 2 output) — only the `publications`
  array and `queries` (to know which mechanistic claim each query targeted), not the whole
  session state.

## Outputs
`data/sessions/<run_id>/verification_report.json`, schema:
```json
{
  "session": "<run_id>",
  "input_count": 448,
  "verified_count": 448,
  "rejected_count": 0,
  "rejection_rate": 0.0,
  "duplicates_removed": 0,
  "underpowered_flag": true,
  "rejections": [
    {"pmid": "...", "reason": "PMID not found in PubMed" }
  ],
  "relevance_scores": [
    {"pmid": "40184040", "target_claim": "Batf3-dependent cDC1 required for lung TRM", "score": 0.9}
  ]
}
```

## Hard constraints
- NEVER mark a PMID verified without an actual PubMed efetch confirming it exists and its
  metadata matches.
- MUST score each paper 0–1 on relevance to the *specific mechanistic claim* it supports,
  not to the disease broadly. A paper about "asthma" in general that is not being used to
  support any specific edge is not "relevant" by default — score it against what Agent 5 will
  actually try to extract from it.
- A 100% accept rate is a defect signal, not a success signal. If `rejection_rate == 0.0`,
  set `underpowered_flag: true` and the session report MUST state that verification should be
  re-run with a stricter relevance threshold before proceeding — do not pass silently.
- Report the rejection rate on every run, even when it is 0%; never omit this metric because
  it looks bad.

## Negative examples
**Real historical failure (Session 001):** `reports/session_001_asthma_kg.md` §2 reports
"Input papers: 448, Accepted (Verified = TRUE): 448, Rejected: 0, Duplicates removed: 0" — a
100% accept rate with an explicit caveat in the same report: "Independent re-fetch
verification was not repeated per-PMID in this session because all records originated from
PubMed efetch. Future sessions should spot-check 5-10% of PMIDs." Under the current spec,
this 0% rejection rate must trigger `underpowered_flag: true` — Session 001 predates that
rule and reported 0% as if it were simply a clean result, which is exactly the failure mode
this constraint exists to prevent from being silently repeated.

## Success criteria
- `rejection_rate` and `underpowered_flag` are both present in every output, regardless of
  value.
- Every verified PMID has a `relevance_scores` entry tied to a specific target claim, not a
  blanket disease-level score.
- Duplicate PMIDs from Agent 2 are caught and removed here if Agent 2 missed any.
