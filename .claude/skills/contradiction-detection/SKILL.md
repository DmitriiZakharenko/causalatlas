---
name: contradiction-detection
description: Use this skill when scanning a knowledge graph for direction-conflicting edges on the same node pair, or logging a new contradiction -- Agent 8's core procedure.
---

# Skill: Contradiction Detection

## When to use this skill
Agent 8, during its full-graph contradiction scan. Also consulted by Agent 9 when a
candidate's classification is C (conflicting literature) and needs to be routed here instead
of to hypothesis generation.

## Procedure

1. **Enumerate every node pair with >=2 edges** in the current graph, programmatically --
   never a hand-picked pair chosen because it looks interesting. Report the coverage
   denominator (e.g. "80 pairs checked" -- see Session 004's real figure) alongside the
   contradiction count, not just the list of contradictions found.
2. For each such pair, compare edge directions/effect signs. A contradiction exists when two
   edges on the same node pair assert opposite causal directions or opposite effect signs
   (e.g. "Batf3 loss -> reduced chronic inflammation" vs. "Batf3 loss -> exacerbated
   inflammation").
3. **Log both sides in full**: both PMIDs, both directions, both species/model systems. Never
   drop one side because it looks "less credible" or "older."
4. **Write a plain-language note on what methodologically differs** between the two studies
   -- model duration, allergen, dose, readout window, species, cell-marker definitions. The
   value of a contradiction entry is in this explanation, not just the fact of disagreement:
   the Batf3 case (PMID 28515363 vs 40184040) only became useful hypothesis material once the
   difference (short vs. long HDM protocol, IL-12-restraint vs. TRM-maintenance mechanism)
   was written down.
5. **Never adjudicate.** Do not add a "winner," "resolution," or "more likely correct" field.
   Silently keeping only one direction, averaging effect sizes, or picking the more-recent or
   higher-powered study as ground truth are all explicitly forbidden -- a contradiction is a
   first-class finding, not a problem to resolve away.

## Gap scan (same agent, related procedure)

- Edges implied by a transitive path but never directly evidenced: mark `UNTESTED`.
- Nodes with only one supporting PMID: mark `POORLY_STUDIED`.
- These are distinct categories -- do not conflate "no direct edge" with "only one paper."

## Output schema

```json
{
  "contradiction_id": "BATF3-CHRONIC-HDM-001",
  "node_pair": ["Batf3", "Airway inflammation (chronic)"],
  "edge_a": {"pmid": "28515363", "direction": "loss -> exacerbated inflammation", "model": "..."},
  "edge_b": {"pmid": "40184040", "direction": "loss -> attenuated inflammation", "model": "..."},
  "distinguishing_note": "Model duration/allergen protocol differs (short chronic protocol in 28515363 vs long-term HDM + TRM-focused readout in 40184040); direction not adjudicated here."
}
```

## Success criteria
- Coverage (pairs checked / total pairs with >=2 edges) is reported, e.g. "80 pairs checked,
  70 contradictions logged" (Session 004's real figures).
- No contradiction entry contains a resolution/winner field.
- Every entry's `distinguishing_note` names a specific methodological difference, not a
  generic "these disagree."
