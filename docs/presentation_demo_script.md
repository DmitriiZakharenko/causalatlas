# LoopFinder Demo Script

English talk track for the 10-minute presentation. This script intentionally uses the graph in the middle of the story, after evidence construction and before hypothesis generation.

## Before the audience arrives

- Open `/presentation` in the presentation tab.
- Keep `/architecture`, `/graphs`, `/evidence`, and `/runs/ibd_20260713T171442Z` in separate tabs.
- On `/graphs`, select the versioned `IBD + NOD2` graph, not an older disease-only graph.
- On `/evidence`, select `ibd_20260713T171442Z`.
- Do not start a live run during the talk. Use the completed artifacts and explain that `/presentation` is read-only.

## 0:00–1:20 — Start with the research failure

**Slides 1–3: `Why one LLM prompt fails` → `The architecture separates these controls`**

**Say:**

"The problem we started with is not simply that biomedical literature is large. The harder problem is deciding whether a proposed disease–gene mechanism is actually new.

If I ask a single language model, ‘Find a novel mechanism connecting this gene to this disease,’ it can produce a fluent and biologically plausible answer. But that answer does not prove that the mechanism is absent from the literature. It does not guarantee balanced search coverage. It does not separate a known component from a genuinely missing causal edge. It does not preserve provenance for every graph relationship, and it rarely states what experiment would falsify the claim.

So the problem is scientific and technical at the same time. We need to establish relevance, novelty, provenance and falsifiability as separate controls. That is why this is a multi-agent system rather than a longer prompt."

**Transition:**

"The architecture follows those failure modes directly."

## 1:20–2:10 — Explain the pipeline before opening other windows

**Slides 4–8: input/output, 13-agent sequence, Agents 01–05, graph layer**

**Say:**

"The input is deliberately small: a disease and a target gene. The output is deliberately structured: verified papers, a causal graph, a novelty audit, a hypothesis, peer-review evidence, and an experiment design.

Agents 01 through 05 build the evidence layer. Agent 1 establishes canonical facts from Reactome, KEGG, UniProt and MyDisease.info. Agent 2 retrieves a mechanism-specific PubMed corpus. Agent 3 verifies the papers. Agent 4 ranks evidence quality. Agent 5 extracts explicit directed causal statements.

Agents 6 through 9 do not invent biology. They structure and stress-test the verified statements: graph construction, feedback loops, topology, contradictions and knowledge gaps.

Only then does the system reach the novelty and hypothesis layer."

## 2:10–3:20 — Show the graph while the audience understands its origin

**Switch to `/graphs`**

**Say:**

"This is the point where I want to show the graph, because now the audience knows where it came from. These nodes are not free-form model associations. They are graph entities backed by extracted evidence and publication provenance.

I can select a node and inspect its neighborhood. The graph is useful for two reasons. First, it makes the disease mechanism legible as a system rather than a list of papers. Second, it exposes where a candidate comes from: which edges are established, which are connected by different papers, and where the missing bridge may be.

For a new disease–gene run, the graph is stored per run. That matters because IBD plus SUCNR1 and IBD plus NOD2 are different analytical objects. A new target must not erase the previous graph."

**Point at the UI:**

- target node and direct neighbors;
- edge direction and evidence strength;
- PMID samples/provenance;
- graph version/run selector;
- pathogenesis view if you want one biological narrative sentence.

**Transition:**

"The graph does not yet mean that we have a new hypothesis. It gives us candidates to challenge."

## 3:20–4:40 — Explain the two Markdown layers

**Return to `/presentation`; jump to `Agent 02` and `PubMed skill` slides**

**Say:**

"Before showing the novelty gate, I want to make the implementation concrete. There are two different Markdown layers in this repository.

An `AGENTS.md` file is an agent contract. It defines the role, inputs, output schema, hard constraints and success criteria. For example, Agent 2 is explicitly a corpus-construction agent. It must use at least three mechanism-specific query strategies, deduplicate PMIDs, record total hits and retrieved papers, and flag temporal skew when one year band exceeds sixty percent. It is not allowed to silently decide relevance or extract mechanisms.

A `SKILL.md` file is a reusable procedure. The PubMed skill defines the actual APIs, rate-limit policy, independent sources, zero-hit handling and the explicit exclusion of Google Scholar. Agent 2 uses PubMed as its primary corpus source. Agents 10 and 12 use PubMed plus an independent structured source for novelty checks.

The distinction is important: the contract says what the agent is responsible for; the skill says how a reusable procedure must be performed."

## 4:40–6:00 — Walk through Agent 10 as the safety-critical component

**Slides: Agent 10 contract → Step 1 → Step 2 → A–E routing**

**Say:**

"Agent 10 is the safety-critical part of the system. Its job is not to generate a clever mechanism. Its job is to prevent a candidate from being called novel before it has earned that label.

Step 1 is a structural originality test. The candidate is compared with the source papers that generated it. If the statement is substantially the same as one paper’s abstract or conclusion, the result is RESTATED. It is routed to the graph with its PMID and stopped before hypothesis generation.

If it survives, Step 2 searches the exact causal chain independently. The system does not search the two nodes separately and pretend that proves the connection. It records the actual queries and results across PubMed and at least one independent structured source such as OpenAlex or Semantic Scholar.

The output is a routing decision. A and B go back to the graph as established or previously published mechanisms. C goes to contradiction handling. Only D and E can reach Agent 11. A zero-hit search is not enough by itself; a D or E classification based on absence needs a second source."

## 6:00–7:15 — Show the real evidence and hypothesis output

**Switch to `/evidence`, select `ibd_20260713T171442Z`**

**Say:**

"Now I will show a completed run rather than a conceptual diagram. This is IBD plus NOD2.

The dashboard separates three statuses: pipeline execution, evidence quality and hypothesis readiness. That separation is intentional. A pipeline can complete all stages and still have no defensible hypothesis.

In this run, the generated hypothesis is H-D001, partially established. The claim is not the generic statement that NOD2 is involved in IBD. The missing bridge is specific: NOD2 risk variants may weaken muramyl-dipeptide-induced NOD2–GIV assembly and downstream cAMP production in intestinal epithelial cells, reducing mucosal barrier integrity.

The UI shows the evidence gap, the specific prediction and the falsification condition. This is where the model’s narrative becomes a scientific object that can be inspected and challenged."

**Show on screen:**

- `H-D001` and class `D`;
- source gap;
- specific prediction;
- falsification criterion;
- evidence metrics and novelty classification.

## 7:15–8:20 — Show the experiment design

**Stay on `/evidence`; scroll to `Agent 13 output`**

**Say:**

"Agent 13 does not merely add a generic ‘test this in a model’ sentence. It translates H-D001 into two experiments.

E1-1 uses patient-derived and CRISPR-isogenic intestinal organoid monolayers. It measures NOD2–GIV assembly, cAMP response and barrier integrity through TEER and FITC-dextran flux.

E1-2 is the rescue experiment. It restores GIV/Gαi signaling or corrects NOD2 and repeats the stimulation and barrier assays. The rescue is important because it tests whether the proposed pathway is causal rather than merely correlated.

The design also includes negative controls and explicit falsification criteria. If the risk variant does not change the pathway, or restoring the pathway does not rescue the barrier phenotype, the hypothesis is rejected."

## 8:20–9:15 — Explain what is actually running under the UI

**Return to `/presentation`; show runtime, artifacts and Codex slides**

**Say:**

"Under the interface, the backend is a FastAPI service. The selected provider runs as a subprocess. With Codex, the command is `codex exec --json` in the repository, and the backend parses JSONL events.

The runtime assembles a prompt from the agent contract, relevant skill documents, compact upstream artifacts, hard budgets and checkpoint paths. It persists raw output and structured session files. The StreamTranslator converts provider-specific events into a small shared UI vocabulary, so React does not need to understand whether an event came from Claude or Codex.

There is an explicit limitation: Codex does not have Claude Code’s native Task tool. The Codex backend therefore uses separate agent calls for language-heavy stages and deterministic Python for graph stages 6 through 9. That gives us a cheaper and more reproducible path, but it is not hidden as exact native subagent parity."

## 9:15–10:00 — Close on the design principle

**Final slide**

**Say:**

"The point of LoopFinder is not to make an LLM sound more confident. It is to make a scientific claim earn its way through a sequence of controls.

The final output is a trace: these papers support these edges; this candidate passed or failed this novelty protocol; these reviewers challenged it; and this experiment could prove it wrong.

So the design principle is simple: do not ask an LLM for a discovery. Ask a sequence of agents to earn one."

## If there is time for one extra window

**Open `/architecture`**

Say:

"This page is the system map. Clicking an agent shows its contract, runtime type, inputs, outputs and loaded skills. The presentation explains the architecture; this page lets you inspect the implementation vocabulary live."

## Questions to anticipate

**Why not use one stronger model?**

"A stronger model can improve individual judgments, but it does not remove the need for independent search, provenance, checkpoints or falsification. The failure is architectural, not only model quality."

**Are D and E discoveries?**

"No. They are eligibility classes. D and E may proceed to hypothesis generation, but peer review can still reject them, and the experiment can still falsify them."

**What happens when the run fails?**

"The run is marked failed or cancelled, the raw event history remains, and completed artifacts/checkpoints are preserved. The UI should never turn a missing downstream artifact into a fabricated hypothesis."

**What is the role of the graph?**

"The graph is the intermediate scientific representation. It connects verified statements, preserves direction and provenance, exposes loops and contradictions, and gives novelty verification a concrete causal chain to challenge."
