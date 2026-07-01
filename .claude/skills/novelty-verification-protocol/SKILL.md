---
name: novelty-verification-protocol
description: Use this skill whenever classifying whether a candidate mechanism/hypothesis is novel (A-E classification) -- Agent 9's core procedure, and every Agent 11 reviewer's independent re-check. The single most safety-critical skill in the system.
---

# Skill: Novelty Verification Protocol

This is the step-by-step procedure behind Agent 9's classification and every Agent 11
reviewer's independent falsification attempt. Agent 9 and every Peer Review reviewer load
this same skill so the standard cannot drift between the two -- if Agent 9 and a reviewer
apply different originality thresholds, the whole gate is unreliable.

## When to use this skill
- Agent 9, on every candidate mechanism before it can be called a hypothesis.
- Every Agent 11 reviewer (A_immunologist, B_systems_biologist, C_editor), independently,
  before voting.

## Step 1 — Structural originality test (before any search)

Ask: does the candidate mechanism appear, in substantially the same form, in the
abstract/conclusion of any **single** source paper already in the corpus?

- **This is a text-comparison question, not a search question.** Read the candidate
  statement against the specific PMID(s) it's built from. If the causal chain the candidate
  asserts is already the stated conclusion of one paper, it is not a hypothesis -- it is a
  **restated finding**.
- If yes: classify `RESTATED`, route to the graph as an established edge with that PMID as
  sole provenance, STOP -- do not proceed to Step 2, do not send to Agent 10.
- If no (the candidate recombines edges from **at least two independent papers** that do not,
  between them, already state this combined path): proceed to Step 2.

**The H1 test (mandatory fixture):** "cDC1 (Batf3-dependent) required for lung TRM sustaining
chronic asthma" is a near-verbatim restatement of PMID 40184040's own abstract conclusion.
Any classification of this statement as anything other than `RESTATED` is a protocol
violation. See Agent 9's AGENTS.md for the full verbatim fixture.

## Step 2 — External literature classification (live search, mandatory)

Use the `pubmed-literature-search` skill's three sources (PubMed E-utilities, Semantic
Scholar, OpenAlex -- never Google Scholar). Run targeted searches for the **specific causal
chain**, not just its component nodes separately (searching "IL-33" and "eosinophil"
separately is not the same as searching for the specific claim that connects them).

Classify into exactly one of:
- **A — Established consensus:** stated as settled in >=2 independent review articles or
  clinical guidelines.
- **B — Previously published:** the specific chain (not just its parts) already appears as a
  primary finding in >=1 paper, in or out of corpus.
- **C — Conflicting literature:** credible papers disagree on direction or existence. Route
  to the `contradiction-detection` skill's log, UNLESS the hypothesis is specifically "which
  condition determines which direction dominates" (a legitimate D-class hypothesis).
- **D — Partially established:** some edges in the chain are shown; the connecting edge(s)
  are not.
- **E — Potentially novel:** no direct statement of this chain found after a documented
  search.

**The H2 test (mandatory fixture):** "IL-33/ILC2/IL-5 couples airway to bone marrow
eosinophilopoiesis" is a recombination of separately-established sub-mechanisms, documented
as consensus since >=2016-2018 (PMIDs 27673511, 29731004, 33669458). Correct classification
is `A`, not `E` -- being a "recombination" does not automatically make something novel if the
combined claim itself is already stated in review literature.

## Mandatory: show your work

Every classification MUST list the actual queries run and the top results checked -- not
just the letter grade. **A grade with no logged search is invalid and must be redone.**
Zero-result searches (`count: 0`) are valid, loggable evidence of absence -- log them exactly
as zero, do not omit a query just because it found nothing.

**Zero-hit results require a second source before being trusted** (see
`pubmed-literature-search` skill's mandatory two-source rule) -- a D/E classification resting
on a single source's zero hits is not yet compliant.

## Gating rule

**Only D or E may proceed to Agent 10.** A and B are relabeled `ESTABLISHED MECHANISM` and
folded into the graph, not the hypothesis list. C is routed to the contradiction log, not
treated as a hypothesis opportunity (except the D-class "which condition dominates"
exception above).

## For Agent 11 reviewers specifically

Each reviewer must run their OWN search, phrased differently from Agent 9's queries AND from
the other two reviewers' queries -- three reviewers running the same query is not three
independent checks. A reviewer who does not run a logged search may not vote ACCEPT,
regardless of how plausible the hypothesis sounds. "Plausible" is never a valid substitute
for a search result in the vote reason.
