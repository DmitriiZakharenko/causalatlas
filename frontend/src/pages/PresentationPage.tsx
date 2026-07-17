import { useEffect, useRef, useState, type ReactNode } from "react";

type Slide = {
  kicker: string;
  title: string;
  body: ReactNode;
  notes: string;
};

const agentContractSnippet = [
  "# Agent 10 — Novelty Verification (MANDATORY, GATING)",
  "",
  "## Role",
  "Before any candidate mechanism may be called a hypothesis,",
  "it must pass the protocol in full.",
  "",
  "## Inputs",
  "- candidate mechanism statement",
  "- relevant graph edges",
  "- canonical_baseline.json",
  "- novelty-verification-protocol skill",
  "",
  "## Outputs",
  "novelty_audit.json entry per candidate",
].join("\n");

const skillSnippet = [
  "# Skill: Novelty Verification Protocol",
  "",
  "## Step 1 — Structural originality test",
  "Does the candidate appear in substantially the same form",
  "in one source paper already in the corpus?",
  "",
  "## Step 2 — External literature classification",
  "Use PubMed, Semantic Scholar, and OpenAlex.",
  "Search the specific causal chain, not separate nodes.",
  "",
  "## Gating rule",
  "Only D or E may proceed to Agent 11.",
].join("\n");

const runtimeSnippet = [
  "inputs = {",
  '  "agent10_novelty_verification": [',
  '    ctx.graph_dir / "knowledge_graph.json",',
  '    ctx.graph_dir / "contradictions.json",',
  '    ctx.graph_dir / "novelty_candidate_manifest.json",',
  '    ctx.session_dir / "canonical_baseline.json",',
  "  ],",
  "}",
  "",
  "prompt_lines += [",
  '  "HARD SEARCH BUDGET:",',
  '  "maximum queries: 8",',
  '  "deadline: 180 seconds",',
  '  "write checkpoint after each search",',
  "]",
].join("\n");

const auditSnippet = [
  "{",
  '  "hypothesis_id": "H-D001",',
  '  "original_statement": "...",',
  '  "step0_canonical_baseline_match": {...},',
  '  "step1_originality": {...},',
  '  "step2_external_searches": [',
  '    {"query": "...", "count": "0", "source": "PubMed"}',
  "  ],",
  '  "classification": "D",',
  '  "eligible_for_hypothesis_generation": true,',
  '  "action": "..."',
  "}",
].join("\n");

const agent02Snippet = [
  "# Agent 2 — Literature Retrieval",
  "",
  "## Role",
  "Retrieve PubMed abstracts for {disease, gene?} across the",
  "full requested publication-year window.",
  "Use MeSH + keyword expansion across multiple complementary",
  "mechanism-specific query strategies.",
  "Agent 2 constructs the corpus; it does not judge relevance,",
  "quality, or mechanisms.",
  "",
  "## Inputs",
  "- disease: str",
  "- gene: str | None",
  "- year_window: [start, end]",
  "- pubmed-literature-search skill",
  "",
  "## Output schema",
  "publications_raw.json:",
  "  session, disease, gene, queries,",
  "  year_band_distribution, year_band_max_share,",
  "  year_band_flag, publications[]",
  "",
  "## Hard constraints",
  "- at least 3 distinct mechanism-specific strategies",
  "- deduplicate PMIDs before writing output",
  "- record total_in_pubmed and retrieved per query",
  "- compute year_band_max_share",
  "- year_band_flag = true if one band exceeds 60%",
  "- never invent PMID, title, or metadata",
  "- use PubMed only; novelty cross-checks belong to Agents 10/12",
  "",
  "## Rate limits",
  "PUBMED_API_KEY: 10 requests/sec",
  "without key: throttle to 3 requests/sec",
  "",
  "## Success criteria",
  "Every PMID is independently verifiable by Agent 03.",
  "The corpus exposes temporal skew instead of hiding it.",
  "",
  "data/sessions/<run_id>/publications_raw.json",
].join("\n");

const pubmedSkillSnippet = [
  "# Skill: PubMed Literature Search",
  "",
  "Source 1: PubMed E-utilities",
  "  esearch -> efetch / esummary",
  "Source 2: Semantic Scholar Graph API",
  "  independent novelty cross-check",
  "Source 3: OpenAlex",
  "  broad coverage + polite pool",
  "",
  "Mandatory: never use Google Scholar.",
  "Mandatory for novelty: at least 2 sources.",
  "Mandatory: zero-hit searches are logged, not hidden.",
].join("\n");

const classificationSnippet = [
  "A  Established consensus  -> graph",
  "B  Previously published   -> graph",
  "C  Conflicting literature -> contradiction log",
  "D  Partially established  -> Agent 11",
  "E  Potentially novel      -> Agent 11",
  "RESTATED                 -> graph + source PMID",
  "",
  "Only D/E may proceed to hypothesis generation.",
  "A/B/C/RESTATED cannot be promoted by plausibility.",
].join("\n");

const artifactSnippet = [
  "data/sessions/<run_id>/",
  "├── canonical_baseline.json       # Agent 01",
  "├── publications_raw.json         # Agent 02",
  "├── publications_verified.json    # Agent 03",
  "├── quality_scores.json            # Agent 04",
  "├── mechanisms_extracted.json     # Agent 05",
  "├── hypotheses.json                # Agent 11",
  "├── peer_review.json               # Agent 12",
  "├── experiment_design.json         # Agent 13",
  "└── checkpoints/agentNN_*.json     # resume state",
].join("\n");

const eventSnippet = [
  "raw Codex JSONL",
  "      |",
  "      v",
  "StreamTranslator.feed(raw_event)",
  "      |",
  "      +--> SQLite event log",
  "      +--> SSE event stream",
  "      +--> React timeline",
  "      +--> run status + evidence summary",
].join("\n");

const graphLayerSnippet = [
  "Agent 05: mechanisms_extracted.json",
  "  explicit source -> target -> relation + PMID provenance",
  "",
  "Agent 06: knowledge_graph.json",
  "  additive merge of nodes and directed edges",
  "  evidence_strength + confidence + PMID list",
  "",
  "Agent 07: loops.json",
  "  feedback cycles and recurrent mechanisms",
  "",
  "Agent 08: network_metrics.json",
  "  topology, architectures, completeness and ranking",
  "",
  "Agent 09: contradictions.json + knowledge_gaps.json",
  "  direction conflicts + missing causal links",
].join("\n");

const hypothesisLayerSnippet = [
  "Agent 10: novelty_audit.json",
  "  candidate -> A/B/C/D/E/RESTATED + search evidence",
  "",
  "Agent 11: hypotheses.json",
  "  source_gap + specific_prediction + falsification",
  "",
  "Agent 12: peer_review.json",
  "  three independent reviewer searches + votes",
  "  ACCEPT / REJECT / UNCERTAIN consensus",
  "",
  "Agent 13: experiment_design.json",
  "  model, method, controls, readouts, rejection criteria",
].join("\n");

const autonomySnippet = [
  "autocomplete",
  "  pause after every agent",
  "",
  "supervised",
  "  pause before Agent 10 and before Agent 13",
  "  human decision persisted in SQLite",
  "",
  "let_it_rip",
  "  no pause points; sequential end-to-end run",
  "",
  "pause marker:",
  "PAUSED_FOR_APPROVAL: <agent> — <reason>",
].join("\n");

const providerSnippet = [
  "LLM_PROVIDER=claude",
  "  Claude CLI subprocess",
  "  native Task/Skill orchestration",
  "",
  "LLM_PROVIDER=codex",
  "  codex exec --json subprocess",
  "  separate agent calls + deterministic graph stages",
  "",
  "shared interface:",
  "  run_agent() / run_orchestrator_stream()",
  "  normalized PipelineEvent types",
].join("\n");

const skillStep1Snippet = [
  "Ask: does the candidate appear in substantially the same form",
  "in the abstract or conclusion of one source paper?",
  "",
  "YES:",
  "  classify RESTATED",
  "  route to graph as established edge",
  "  cite the PMID as sole provenance",
  "  STOP — do not run Step 2",
  "  STOP — do not send to Agent 11",
  "",
  "NO:",
  "  recombine edges from at least two independent papers",
  "  that do not already state the combined path.",
].join("\n");

const skillStep2Snippet = [
  "Search the specific chain, not separate component nodes.",
  "",
  "PubMed E-utilities       primary biomedical index",
  "Semantic Scholar Graph   independent cross-check",
  "OpenAlex                 broad coverage cross-check",
  "",
  "Never use Google Scholar.",
  "Every query and top result must be logged.",
  "A zero-hit D/E decision needs a second independent source.",
].join("\n");

const skillRoutingSnippet = [
  "A  Established consensus  -> graph; never a hypothesis",
  "B  Previously published   -> graph; never a hypothesis",
  "C  Conflicting literature -> contradiction log",
  "D  Partially established  -> Agent 11 may generate",
  "E  Potentially novel      -> Agent 11 may generate",
  "",
  "Agent 12 reviewers repeat the search independently.",
  "A reviewer without a logged search cannot vote ACCEPT.",
].join("\n");

const slides: Slide[] = [
  {
    kicker: "The research problem",
    title: "Why one LLM prompt fails",
    body: <><p className="presentation-lead">The task is not “summarize the literature.” It is: find a causal gap, prove that it is not already published, and turn it into a falsifiable experiment.</p><div className="presentation-quote">A plausible answer is easy. An auditable novelty claim is a systems problem.</div><div className="presentation-problem-grid"><div><b>Scientific question</b><span>Is this disease–gene mechanism already known, partially known, or genuinely missing?</span></div><div><b>Engineering question</b><span>Can every claim be traced through papers, graph edges, agent outputs and decisions?</span></div><div><b>Experimental question</b><span>What result would prove the proposed mechanism wrong?</span></div></div></>,
    notes: "Do not start with the UI. Start with the research problem: relevance, novelty and falsifiability are separate questions that a single response tends to collapse into one confident narrative.",
  },
  {
    kicker: "Why the obvious solution fails",
    title: "Five controls one prompt cannot provide",
    body: <div className="presentation-problem-grid presentation-problem-grid--five"><div><b>Search coverage</b><span>The model cannot guarantee balanced year bands, query diversity or complete metadata.</span></div><div><b>Corpus bias</b><span>The papers that generated a candidate cannot independently clear its novelty.</span></div><div><b>Known vs new</b><span>Component facts can be known while their full chain is also already published.</span></div><div><b>Provenance</b><span>A fluent claim does not create a PMID-backed directed graph edge.</span></div><div><b>Falsification</b><span>A narrative answer rarely specifies a result that would reject it.</span></div></div>,
    notes: "This is why the project needs a system, not a longer prompt. Each failure mode gets a separate contract, artifact, check or gate.",
  },
  {
    kicker: "Design response",
    title: "The architecture separates these controls",
    body: <div className="presentation-phase-grid"><div><b>01–05</b><strong>Build evidence</strong><span>Retrieve, verify, rank and extract explicit findings.</span></div><div><b>06–09</b><strong>Structure evidence</strong><span>Build graph, analyze loops, topology and contradictions.</span></div><div><b>10</b><strong>Challenge novelty</strong><span>Classify the specific chain with independent searches.</span></div><div><b>11–12</b><strong>Challenge the hypothesis</strong><span>Generate only eligible candidates and run peer review.</span></div><div><b>13</b><strong>Design the test</strong><span>Specify model, controls, readouts and falsification.</span></div></div>,
    notes: "This slide answers why the architecture is complex. Complexity is assigned to distinct scientific controls rather than hidden inside one prompt.",
  },
  {
    kicker: "CausalAtlas",
    title: "Input: disease + gene. Output: evidence trail.",
    body: <><div className="presentation-flow"><span>IBD + NOD2</span><b>literature</b><span>verified papers</span><b>graph</b><span>novelty audit</span><b>review</b><span>H-D001 + E1/E2</span></div><div className="presentation-output-grid"><div><b>Not the output</b><span>One confident paragraph with no source trail.</span></div><div><b>Actual output</b><span>Artifacts, classifications, predictions, controls and falsification criteria.</span></div></div></>,
    notes: "The input is small: disease plus target. The output is not a paragraph. It is a chain of auditable artifacts that can be inspected stage by stage.",
  },
  {
    kicker: "Architecture",
    title: "The 13-agent execution sequence",
    body: <div className="presentation-agent-grid">{["01 Baseline", "02 Literature", "03 Verify", "04 Quality", "05 Extract", "06 Graph", "07 Loops", "08 Topology", "09 Contradictions", "10 Novelty gate", "11 Hypothesis", "12 Peer review", "13 Experiment"].map((agent, index) => <div className={`presentation-agent presentation-agent--${index >= 9 ? "orange" : index >= 5 ? "blue" : "teal"}`} key={agent}><small>{String(index + 1).padStart(2, "0")}</small><strong>{agent.replace(/^\d+ /, "")}</strong></div>)}</div>,
    notes: "Stress sequential dependencies. Retrieval cannot independently validate its own novelty. Graph construction needs verified evidence. Experiment design needs a surviving hypothesis.",
  },
  {
    kicker: "Agents 01–05 / evidence layer",
    title: "What Agents 01–05 produce",
    body: <div className="presentation-phase-grid"><div><b>01</b><strong>Canonical baseline</strong><span>Reactome, KEGG, UniProt, MyDisease.info</span><code>canonical_baseline.json</code></div><div><b>02</b><strong>Literature retrieval</strong><span>Mechanism-specific PubMed corpus</span><code>publications_raw.json</code></div><div><b>03</b><strong>Publication verification</strong><span>PMID, metadata and relevance checks</span><code>verification_report.json</code></div><div><b>04</b><strong>Quality filter</strong><span>Evidence strength and translation limits</span><code>quality_scores.json</code></div><div><b>05</b><strong>Mechanistic extraction</strong><span>Explicit directed causal statements</span><code>mechanisms_extracted.json</code></div></div>,
    notes: "This is the evidence layer. None of these agents is allowed to jump directly to a novel hypothesis. Their job is to create a clean, provenance-aware input for the graph layer.",
  },
  {
    kicker: "Agents 06–09 / graph layer",
    title: "How Agents 06–09 build the graph",
    body: <div className="presentation-code"><div className="presentation-code__bar"><span>graph layer outputs</span><i>deterministic structure + analysis</i></div><pre>{graphLayerSnippet}</pre><div className="presentation-code__callout">The graph does not replace evidence. Every edge keeps provenance so the researcher can trace it back to source papers.</div></div>,
    notes: "Explain the difference between extraction and graph analysis. Agent 05 extracts explicit statements. Agents 06–09 compute structure, loops, topology, contradictions and gaps. In Codex mode these stages are intentionally deterministic for cost and reproducibility.",
  },
  {
    kicker: "Agents 10–13 / hypothesis layer",
    title: "How Agents 10–13 gate experiments",
    body: <div className="presentation-code"><div className="presentation-code__bar"><span>hypothesis layer outputs</span><i>promotion requires evidence</i></div><pre>{hypothesisLayerSnippet}</pre><div className="presentation-code__callout">Agent 13 is not allowed to design an experiment for a rejected or unsupported candidate.</div></div>,
    notes: "This is the core scientific control. Agent 11 proposes; Agent 12 independently attacks; Agent 13 only translates a surviving candidate into a validation plan.",
  },
  {
    kicker: "Agent 02 / contract excerpt",
    title: "How Agent 02 builds the corpus",
    body: <div className="presentation-code"><div className="presentation-code__bar"><span>agents/agent02_literature_retrieval/AGENTS.md</span><i>retrieval contract</i></div><pre>{agent02Snippet}</pre><div className="presentation-code__callout">The separation is intentional: Agent 02 finds papers; Agents 03–05 decide whether and how they can support a causal edge.</div></div>,
    notes: "Point out that the contract explicitly forbids relevance judgment and mechanism extraction. This prevents the first search agent from silently deciding the scientific conclusion.",
  },
  {
    kicker: "PubMed Literature Search skill",
    title: "What the PubMed skill enforces",
    body: <div className="presentation-code"><div className="presentation-code__bar"><span>skills/pubmed-literature-search/SKILL.md</span><i>reusable search procedure</i></div><pre>{pubmedSkillSnippet}</pre><div className="presentation-code__callout">The skill is shared by Agent 02, Agent 10 and Agent 12, but each uses it for a different search purpose.</div></div>,
    notes: "Agent 02 uses PubMed as the primary corpus. Agent 10 and Agent 12 use PubMed plus an independent structured source for novelty. The same skill encodes the no-Google-Scholar rule and zero-hit handling.",
  },
  {
    kicker: "Context engineering",
    title: "Four layers, four responsibilities",
    body: <div className="presentation-layers"><div><code>backend/app/*.py</code><strong>Runtime</strong><span>CLI, JSONL, SQLite, API, SSE</span></div><div><code>agents/*/AGENTS.md</code><strong>Contracts</strong><span>Role, inputs, outputs, constraints</span></div><div><code>skills/*/SKILL.md</code><strong>Procedures</strong><span>Search and safety protocols</span></div><div><code>data/sessions/*</code><strong>State</strong><span>Artifacts and checkpoints</span></div></div>,
    notes: "This is a key technical distinction. Markdown is not decoration: it is the canonical context layer loaded into agent execution. Python owns lifecycle and persistence.",
  },
  {
    kicker: "Autonomy control",
    title: "Three autonomy modes",
    body: <div className="presentation-code"><div className="presentation-code__bar"><span>agents/agent00_orchestrator/AGENTS.md</span><i>autonomy protocol</i></div><pre>{autonomySnippet}</pre><div className="presentation-code__callout">Approve, reject or edit decisions are recorded as interventions and the same session can resume.</div></div>,
    notes: "Explain that autonomy is an execution policy. It does not weaken novelty rules. In supervised mode the human signs off before the high-risk novelty and experiment stages.",
  },
  {
    kicker: "Provider abstraction",
    title: "Two providers, one artifact contract",
    body: <div className="presentation-code"><div className="presentation-code__bar"><span>backend/app/llm_cli.py + provider backends</span><i>runtime selection</i></div><pre>{providerSnippet}</pre><div className="presentation-code__callout">The frontend consumes normalized events; provider-specific limitations stay in the backend.</div></div>,
    notes: "Be explicit: Claude has native Task/Skill orchestration. Codex does not. The system preserves the same artifact contracts and UI event model while changing the execution strategy.",
  },
  {
    kicker: "Inside one agent",
    title: "Agent 10's contract",
    body: <div className="presentation-code"><div className="presentation-code__bar"><span>agents/agent10_novelty_verification/AGENTS.md</span><i>agent contract</i></div><pre>{agentContractSnippet}</pre><div className="presentation-code__callout">This file defines the job boundary. It does not implement HTTP, persistence, or UI.</div></div>,
    notes: "Show that the agent is not a name in a diagram. It has a versioned role contract, explicit inputs, explicit outputs, and a mandatory gate. The Markdown is read as runtime context by the selected backend.",
  },
  {
    kicker: "Inside one skill",
    title: "The novelty Skill",
    body: <div className="presentation-code"><div className="presentation-code__bar"><span>skills/novelty-verification-protocol/SKILL.md · 87 lines / 750 words</span><i>shared method</i></div><pre>{skillSnippet}</pre><div className="presentation-code__callout">Agent 10 and all three Agent 12 reviewers load the same file. The contract says who; the Skill says how.</div></div>,
    notes: "This is only the overview. The next three slides unpack the actual procedure. Make clear that the skill is a real 87-line procedural artifact, not a one-line prompt hint.",
  },
  {
    kicker: "Novelty Skill / Step 1",
    title: "Step 1: detect restatements",
    body: <div className="presentation-code"><div className="presentation-code__bar"><span>novelty-verification-protocol/SKILL.md</span><i>structural originality</i></div><pre>{skillStep1Snippet}</pre><div className="presentation-code__callout">The H1 fixture makes this executable: a near-verbatim PMID 40184040 conclusion must be RESTATED.</div></div>,
    notes: "This is a text-comparison test before external search. It prevents the system from calling a paper's own conclusion a new hypothesis.",
  },
  {
    kicker: "Novelty Skill / Step 2",
    title: "Step 2: search the causal chain",
    body: <div className="presentation-code"><div className="presentation-code__bar"><span>novelty-verification-protocol + pubmed-literature-search</span><i>external classification</i></div><pre>{skillStep2Snippet}</pre><div className="presentation-code__callout">Searching “IL-33” and “eosinophil” separately is not evidence about an IL-33 → eosinophil → feedback chain.</div></div>,
    notes: "This is where the skill prevents false novelty from index gaps. The query must target the connection, and absence in one source cannot be treated as proof.",
  },
  {
    kicker: "Novelty Skill / routing",
    title: "A–E routing rules",
    body: <div className="presentation-code"><div className="presentation-code__bar"><span>novelty-verification-protocol/SKILL.md</span><i>hard routing rule</i></div><pre>{skillRoutingSnippet}</pre><div className="presentation-code__callout">This is a routing policy, not a confidence score. Plausibility cannot override the route.</div></div>,
    notes: "Close the skill walkthrough by showing its operational effect: it changes the next legal transition in the pipeline and constrains peer review.",
  },
  {
    kicker: "Runtime wiring",
    title: "Python assembles the call",
    body: <div className="presentation-code"><div className="presentation-code__bar"><span>backend/app/codex_pipeline.py</span><i>prompt assembly</i></div><pre>{runtimeSnippet}</pre><div className="presentation-code__callout">The runtime injects only relevant artifacts and enforces the budget before the model call.</div></div>,
    notes: "This is the bridge between declarative context and executable runtime. The runner selects inputs, loads skill docs, adds budgets and checkpoints, then calls the provider.",
  },
  {
    kicker: "Machine-readable hand-off",
    title: "The novelty audit hand-off",
    body: <div className="presentation-code"><div className="presentation-code__bar"><span>novelty_audit.json</span><i>persisted artifact</i></div><pre>{auditSnippet}</pre><div className="presentation-code__callout">Agent 11 receives this artifact. The UI can expose the evidence trail without replaying the model conversation.</div></div>,
    notes: "This is the important hand-off. The next agent does not receive an opaque previous answer. It receives a schema with classification, search evidence, eligibility, and action.",
  },
  {
    kicker: "Session state",
    title: "Session artifacts and checkpoints",
    body: <div className="presentation-code"><div className="presentation-code__bar"><span>data/sessions/&lt;run_id&gt;/</span><i>durable state</i></div><pre>{artifactSnippet}</pre><div className="presentation-code__callout">A failed or interrupted run can continue from checkpoints instead of repeating every search.</div></div>,
    notes: "This is where the system becomes more than a chain of prompts. The session directory is the durable boundary between agents and the audit surface for the UI.",
  },
  {
    kicker: "Runtime to UI",
    title: "Raw events become UI state",
    body: <div className="presentation-code"><div className="presentation-code__bar"><span>backend/app/orchestrator.py + frontend/src/api/sse.ts</span><i>event path</i></div><pre>{eventSnippet}</pre><div className="presentation-code__callout">The UI never needs to understand provider-specific Codex or Claude event formats.</div></div>,
    notes: "StreamTranslator normalizes provider events into skill_loaded, agent_started, agent_completed, run_completed, run_failed and run_paused. SQLite makes the event history durable; SSE makes it live.",
  },
  {
    kicker: "Agent 10 / safety gate",
    title: "Agent 10's promotion gate",
    body: <div className="presentation-gate"><div><b>0</b><span>Canonical baseline</span></div><i>→</i><div><b>1</b><span>Restatement test</span></div><i>→</i><div><b>2</b><span>Independent search</span></div><i>→</i><div className="presentation-gate__result"><b>A–E</b><span>Only D/E proceed</span></div></div>,
    notes: "Agent 10 checks canonical databases first, then structural originality, then independent PubMed plus OpenAlex or Semantic Scholar searches. It never trusts only the corpus that generated the candidate.",
  },
  {
    kicker: "Agent 10 / classification output",
    title: "What A–E means",
    body: <div className="presentation-code"><div className="presentation-code__bar"><span>novelty-verification-protocol/SKILL.md</span><i>classification policy</i></div><pre>{classificationSnippet}</pre><div className="presentation-code__callout">A D/E label is a candidate for investigation, not a guarantee that the final hypothesis will survive peer review.</div></div>,
    notes: "Spend time here. A means consensus, B means the specific chain is published, C means contradiction, D means a missing bridge, E means no direct chain found after documented search. RESTATED is its own early stop.",
  },
  {
    kicker: "Real run / IBD + NOD2",
    title: "H-D001: NOD2 to barrier",
    body: <div className="presentation-hypothesis"><div className="presentation-badge">D · PARTIALLY ESTABLISHED</div><p>NOD2 risk variants may weaken muramyl-dipeptide-induced NOD2–GIV assembly and downstream cAMP production in intestinal epithelial cells, reducing mucosal barrier integrity.</p><div className="presentation-chain"><span>NOD2 variant</span><b>→</b><span>NOD2–GIV / cAMP</span><b>→</b><span>barrier integrity</span></div></div>,
    notes: "Explain the gap: NOD2 variants and the NOD2–GIV/cAMP axis are individually supported, but the variant-to-axis bridge in intestinal tissue is not established.",
  },
  {
    kicker: "Agent 13",
    title: "E1-1 measures; E1-2 rescues",
    body: <div className="presentation-experiments"><article><b>E1-1</b><strong>Measure the bridge</strong><span>Isogenic intestinal organoids. NOD2–GIV assembly, cAMP, TEER and FITC-dextran flux.</span></article><article><b>E1-2</b><strong>Test rescue</strong><span>Restore GIV/Gαi signaling or correct NOD2. Repeat stimulation and barrier assays.</span></article><footer>Falsification: no genotype effect, or no pathway-specific rescue.</footer></div>,
    notes: "The output is not only a prediction. It includes controls, readouts, and a pre-stated condition that would reject the hypothesis.",
  },
  {
    kicker: "Codex backend",
    title: "Codex hybrid execution",
    body: <div className="presentation-terminal"><span>LLM_PROVIDER=codex</span><code>codex exec --json -C &lt;repo&gt; \\</code><code>  --dangerously-bypass-approvals-and-sandbox</code><div className="terminal-arrow">JSONL → translator → SQLite → SSE → UI</div></div>,
    notes: "Claude keeps native Task and Skill orchestration. Codex has no native Claude Code Task tool, so the hybrid runner uses separate agent calls for language-heavy stages and deterministic Python for graph stages 6–9. It is cheaper and explicit about its limitation.",
  },
  {
    kicker: "Reliability",
    title: "Execution vs readiness",
    body: <div className="presentation-reliability"><div><strong>Raw JSONL</strong><span>What the agent actually returned</span></div><b>→</b><div><strong>Session artifact</strong><span>What downstream agents received</span></div><b>→</b><div><strong>UI audit</strong><span>What the researcher can inspect</span></div></div>,
    notes: "Every run has checkpoints, budgets and persisted hand-offs. Pipeline completion and scientific readiness are intentionally separate statuses.",
  },
  {
    kicker: "Closing principle",
    title: "Earn the discovery claim",
    body: <><p className="presentation-closing">Ask a sequence of agents to earn one.</p><div className="presentation-closing-sub">Evidence first. Novelty second. Falsification always.</div></>,
    notes: "End on the design principle. The output is a trace: papers, edges, gate, reviewers, and an experiment that could prove the claim wrong.",
  },
];

export default function PresentationPage() {
  const [slide, setSlide] = useState(0);
  const [showNotes, setShowNotes] = useState(false);
  const presentationRef = useRef<HTMLDivElement>(null);
  const active = slides[slide];

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "ArrowRight" || event.key === " ") setSlide((value) => Math.min(value + 1, slides.length - 1));
      if (event.key === "ArrowLeft") setSlide((value) => Math.max(value - 1, 0));
      if (event.key.toLowerCase() === "n") setShowNotes((value) => !value);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const enterFullscreen = () => presentationRef.current?.requestFullscreen?.();

  return <div ref={presentationRef} className="presentation-shell">
    <div className="presentation-topbar"><span className="presentation-brand">LOOPFINDER <i>10 MINUTES</i></span><span>{String(slide + 1).padStart(2, "0")} / {String(slides.length).padStart(2, "0")}</span><div><button onClick={() => setShowNotes((value) => !value)}>{showNotes ? "Hide notes" : "Show notes"} <kbd>N</kbd></button><button onClick={enterFullscreen}>Fullscreen</button></div></div>
    <main className="presentation-stage" aria-live="polite"><section className="presentation-slide"><div className="presentation-slide__kicker">{active.kicker}</div><h1>{active.title}</h1><div className="presentation-slide__body">{active.body}</div>{showNotes && <aside className="presentation-notes"><b>Speaker notes</b><span>{active.notes}</span></aside>}</section></main>
    <div className="presentation-controls"><button onClick={() => setSlide((value) => Math.max(value - 1, 0))} disabled={slide === 0}>←</button><input aria-label="Presentation slide" type="range" min="0" max={slides.length - 1} value={slide} onChange={(event) => setSlide(Number(event.target.value))} /><button onClick={() => setSlide((value) => Math.min(value + 1, slides.length - 1))} disabled={slide === slides.length - 1}>→</button></div>
  </div>;
}
