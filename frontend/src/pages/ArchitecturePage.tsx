import { useEffect, useMemo, useState } from "react";

type Agent = {
  id: string;
  number: string;
  title: string;
  short: string;
  phase: string;
  color: string;
  skills: string[];
  input: string;
  output: string;
  detail: string;
};

type SkillInfo = { name: string; purpose: string; loaded: string; output: string };

const skillInfo: Record<string, SkillInfo> = {
  "canonical-baseline-lookup": { name: "Canonical baseline lookup", purpose: "Fetches established mechanisms from Reactome, KEGG, UniProt and MyDisease.info.", loaded: "Before Agent 01", output: "Canonical identifiers and consensus edges" },
  "pubmed-literature-search": { name: "PubMed literature search", purpose: "Builds mechanism-specific evidence corpora and performs independent literature cross-checks.", loaded: "Before Agents 02, 10 and 12", output: "Verified search results and logged queries" },
  "graph-export-visualization": { name: "Graph export & visualization", purpose: "Applies graph provenance, noise-filtering and export conventions so visual outputs remain auditable.", loaded: "Before Agents 06 and 08", output: "GraphML/GEXF/SVG-ready graph artifacts" },
  "cross-disease-motif-analysis": { name: "Cross-disease motif analysis", purpose: "Compares disease graphs to separate shared immune motifs from disease-specific architecture.", loaded: "Before Agent 08 when another graph exists", output: "Shared and disease-specific motifs" },
  "contradiction-detection": { name: "Contradiction detection", purpose: "Scans the graph for direction conflicts and records missing causal links as knowledge gaps.", loaded: "Before Agent 09", output: "Contradiction log and gap report" },
  "novelty-verification-protocol": { name: "Novelty verification protocol", purpose: "Runs the mandatory structural and external-literature checks behind the A–E novelty gate.", loaded: "Before Agents 10 and 12", output: "Auditable novelty classification" },
};

const agents: Agent[] = [
  { id: "agent01_baseline_canonical_knowledge", number: "01", title: "Canonical baseline", short: "Ground truth", phase: "Evidence", color: "#0f766e", skills: ["canonical-baseline-lookup"], input: "Disease + target", output: "Canonical mechanisms", detail: "Anchors the run in established Reactome, KEGG, UniProt and MyDisease knowledge before literature search begins." },
  { id: "agent02_literature_retrieval", number: "02", title: "Literature retrieval", short: "Find papers", phase: "Evidence", color: "#0f766e", skills: ["pubmed-literature-search"], input: "Target + mechanism queries", output: "Candidate corpus", detail: "Builds a mechanism-specific corpus and records complete publication metadata for downstream verification." },
  { id: "agent03_publication_verification", number: "03", title: "Publication verification", short: "Verify sources", phase: "Evidence", color: "#0f766e", skills: [], input: "Candidate corpus", output: "Verified papers", detail: "Checks that every paper is real, relevant and usable as evidence rather than trusting search results blindly." },
  { id: "agent04_quality_filter", number: "04", title: "Quality filter", short: "Grade evidence", phase: "Evidence", color: "#0f766e", skills: [], input: "Verified papers", output: "Quality-ranked evidence", detail: "Filters weak or non-translational evidence and flags species, model and replication limitations." },
  { id: "agent05_mechanistic_extraction", number: "05", title: "Mechanistic extraction", short: "Extract edges", phase: "Evidence", color: "#0f766e", skills: [], input: "Quality-ranked evidence", output: "Causal statements", detail: "Extracts only explicitly supported biological relationships with provenance and direction." },
  { id: "agent06_graph_builder", number: "06", title: "Graph builder", short: "Build graph", phase: "Structure", color: "#2563eb", skills: ["graph-export-visualization"], input: "Causal statements", output: "Knowledge graph", detail: "Merges evidence additively into the disease graph while preserving session and PMID provenance." },
  { id: "agent07_loop_discovery", number: "07", title: "Loop discovery", short: "Find motifs", phase: "Structure", color: "#2563eb", skills: [], input: "Knowledge graph", output: "Feedback loops", detail: "Surfaces recurrent causal motifs and closed feedback loops that may organize disease biology." },
  { id: "agent08_topology_analysis", number: "08", title: "Topology analysis", short: "Rank architectures", phase: "Structure", color: "#2563eb", skills: ["graph-export-visualization", "cross-disease-motif-analysis"], input: "Graph + loops", output: "Ranked architectures", detail: "Ranks graph architectures by completeness, evidence and topology, while preserving partial structures." },
  { id: "agent09_contradiction_gap_detection", number: "09", title: "Contradictions & gaps", short: "Stress-test graph", phase: "Structure", color: "#2563eb", skills: ["contradiction-detection"], input: "Graph + architectures", output: "Contradictions + gaps", detail: "Finds direction conflicts and missing links before the system is allowed to propose hypotheses." },
  { id: "agent10_novelty_verification", number: "10", title: "Novelty verification", short: "Gate novelty", phase: "Hypothesis", color: "#c2410c", skills: ["pubmed-literature-search", "novelty-verification-protocol"], input: "Candidate mechanisms", output: "A–E classifications", detail: "The safety gate: independently searches the literature and classifies candidates before they can be called novel." },
  { id: "agent11_hypothesis_generation", number: "11", title: "Hypothesis generation", short: "Compose hypotheses", phase: "Hypothesis", color: "#c2410c", skills: [], input: "Eligible D/E candidates", output: "Mechanistic hypotheses", detail: "Recombines existing graph edges into testable hypotheses without inventing unsupported biology." },
  { id: "agent12_peer_review", number: "12", title: "Peer review", short: "Independent review", phase: "Hypothesis", color: "#c2410c", skills: ["pubmed-literature-search", "novelty-verification-protocol"], input: "Hypotheses + evidence", output: "Review votes", detail: "Three independent perspectives attempt to falsify novelty, evidence quality and contradiction consistency." },
  { id: "agent13_experiment_design", number: "13", title: "Experiment design", short: "Make testable", phase: "Action", color: "#7c3aed", skills: [], input: "Accepted hypotheses", output: "Validation plan", detail: "Turns surviving hypotheses into experiments matched to species, model system, readouts and controls." },
];

const phases = [
  { label: "Evidence layer", range: "01–05", color: "#0f766e" },
  { label: "Graph layer", range: "06–09", color: "#2563eb" },
  { label: "Hypothesis layer", range: "10–12", color: "#c2410c" },
  { label: "Action layer", range: "13", color: "#7c3aed" },
];

const mapAgents = [...agents.slice(0, 7), ...agents.slice(7).reverse()];
const skillAtlas = Object.entries(skillInfo).map(([id, info]) => ({ id, info, users: agents.filter((agent) => agent.skills.includes(id)).map((agent) => agent.number) }));
const PLAYBACK_STEP_MS = 3500;
const deterministicAgents = new Set([
  "agent06_graph_builder",
  "agent07_loop_discovery",
  "agent08_topology_analysis",
  "agent09_contradiction_gap_detection",
]);
const runtimeType = (agentId: string) => deterministicAgents.has(agentId) ? "Deterministic graph stage" : "LLM-backed Codex agent";
const agentExamples: Record<string, string> = {
  agent01_baseline_canonical_knowledge: "For IBD + SUCNR1: resolve canonical SUCNR1 identity, known ligand/receptor biology and established inflammatory pathways before searching papers.",
  agent02_literature_retrieval: "Search mechanism-specific chains such as SUCNR1 → succinate sensing → macrophage activation, not only the broad query IBD SUCNR1.",
  agent03_publication_verification: "Reject a search hit with missing PMID metadata, wrong disease context or no primary mechanistic evidence.",
  agent04_quality_filter: "Keep a human or well-annotated translational study above an unreplicated cell-line claim and preserve the reason for the ranking.",
  agent05_mechanistic_extraction: "Turn an explicit result into a causal statement such as SUCNR1 activation increases a defined inflammatory readout in a named cell type.",
  agent06_graph_builder: "Merge the new SUCNR1 edge into the IBD graph without deleting prior PMID provenance or overwriting earlier sessions.",
  agent07_loop_discovery: "Detect a supported feedback motif where metabolite accumulation, receptor sensing and inflammatory tissue response reinforce one another.",
  agent08_topology_analysis: "Rank a complete, multi-edge architecture above a visually plausible but evidence-sparse partial pathway.",
  agent09_contradiction_gap_detection: "Flag two papers that report opposite SUCNR1 directions on the same node pair and name the missing context needed to resolve it.",
  agent10_novelty_verification: "Search whether a proposed SUCNR1 → fibro-inflammatory remodeling chain is already directly published, then assign the required A–E class.",
  agent11_hypothesis_generation: "Compose a testable hypothesis only from eligible graph edges, for example a cell-specific intervention with a predicted readout.",
  agent12_peer_review: "Three independent reviewers try to falsify novelty, evidence quality and contradiction consistency before promotion to experiment design.",
  agent13_experiment_design: "Specify model, perturbation, controls and readouts that could distinguish the proposed SUCNR1 mechanism from a generic inflammation effect.",
};

const orchestrator = { title: "Agent 00 · Orchestrator", detail: "The control plane never performs biology itself. It sequences the 13 workers, loads the relevant skill before each dispatch, persists every output and enforces autonomy checkpoints.", example: "Dispatch Agent 02 only after Agent 01 has persisted its canonical baseline; pause or resume the same run when a supervised checkpoint requires human input." };

export default function ArchitecturePage() {
  const [selectedId, setSelectedId] = useState(agents[9].id);
  const [playing, setPlaying] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const selected = agents.find((agent) => agent.id === selectedId) ?? agents[0];

  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => {
      setActiveIndex((current) => {
        if (current >= agents.length - 1) {
          setPlaying(false);
          return 0;
        }
        return current + 1;
      });
    }, PLAYBACK_STEP_MS);
    return () => window.clearInterval(timer);
  }, [playing]);

  useEffect(() => {
    if (playing) setSelectedId(agents[activeIndex].id);
  }, [activeIndex, playing]);

  const completedCount = useMemo(() => Math.max(activeIndex, 0), [activeIndex]);

  return (
    <div className="page page--architecture">
      <section className="architecture-hero">
        <div>
          <p className="eyebrow">CausalAtlas / system map</p>
          <h1>From evidence to experiment</h1>
          <p className="architecture-hero__copy">
            A sequential, evidence-gated pipeline that turns a disease–target question into a causal graph and a testable mechanistic hypothesis.
          </p>
        </div>
        <div className="architecture-hero__actions">
          <button className={`button button--primary ${playing ? "is-playing" : ""}`} onClick={() => setPlaying((value) => !value)}>
            {playing ? "Pause flow" : "Play data flow"}
          </button>
          <span className="architecture-hero__hint">13 agents · 6 reusable skills · sequential hand-off</span>
        </div>
      </section>

      <section className="architecture-stats" aria-label="Pipeline summary">
        <div><strong>13</strong><span>specialized agents</span></div>
        <div><strong>4</strong><span>gated layers</span></div>
        <div><strong>6</strong><span>reusable skills</span></div>
        <div><strong>A–E</strong><span>novelty gate</span></div>
      </section>

      <section className="architecture-workspace">
        <div className="architecture-map-card">
          <div className="section-heading">
            <div><p className="eyebrow">Orchestrated sequence</p><h2>Agent metro map</h2></div>
            <div className="flow-counter"><strong>{String(completedCount + 1).padStart(2, "0")}</strong><span> / 13 stations</span></div>
          </div>
          <div className="phase-legend">
            {phases.map((phase) => <span key={phase.label}><i style={{ background: phase.color }} />{phase.label} <small>{phase.range}</small></span>)}
          </div>
          <div className="orchestrator-card"><div className="orchestrator-card__icon">00</div><div><div className="orchestrator-card__title"><strong>{orchestrator.title}</strong><span>CONTROL PLANE</span></div><p>{orchestrator.detail}</p><div className="orchestrator-card__example"><b>Example</b>{orchestrator.example}</div></div><div className="orchestrator-card__outputs"><span>dispatch</span><span>persist</span><span>pause / resume</span></div></div>
          <div className="agent-map">
            <div className="agent-line agent-line--top" aria-hidden="true" />
            <div className="agent-line agent-line--bottom" aria-hidden="true" />
            <div className="agent-route-bridge" aria-hidden="true" />
            {mapAgents.map((agent) => {
              const index = agents.findIndex((item) => item.id === agent.id);
              const isActive = index === activeIndex && playing;
              const isPassed = index < activeIndex;
              return (
                <button key={agent.id} className={`agent-stop ${selectedId === agent.id ? "is-selected" : ""} ${isActive ? "is-active" : ""} ${isPassed ? "is-passed" : ""}`} style={{ borderTopColor: agent.color }} onClick={() => { setSelectedId(agent.id); setActiveIndex(index); }}>
                  <span className="agent-stop__number" style={{ borderColor: agent.color, color: agent.color }}>{agent.number}</span>
                  <span className="agent-stop__body"><strong>{agent.title}</strong><small>{agent.short}</small></span>
                  <span className={`runtime-badge runtime-badge--${deterministicAgents.has(agent.id) ? "deterministic" : "llm"}`}>{deterministicAgents.has(agent.id) ? "deterministic" : "Codex LLM"}</span>
                  <span className="agent-stop__transfer">{agent.output}</span>
                  {agent.skills.length > 0 && <span className="agent-stop__skill">{agent.skills.length} skill module{agent.skills.length > 1 ? "s" : ""}</span>}
                </button>
              );
            })}
          </div>
          <div className="playback-controls">
            <button className={`button button--primary playback-controls__button ${playing ? "is-playing" : ""}`} onClick={() => setPlaying((value) => !value)}>{playing ? "Pause" : "Play flow"}</button>
            <input aria-label="Pipeline playback position" type="range" min="0" max={agents.length - 1} step="1" value={activeIndex} onChange={(event) => { const index = Number(event.target.value); setActiveIndex(index); setSelectedId(agents[index].id); setPlaying(false); }} />
            <span className="playback-controls__label">Agent {agents[activeIndex].number}: {agents[activeIndex].short} · 3.5 sec / step</span>
          </div>
          <div className="playback-explain" aria-live="polite"><div className="playback-explain__title"><span>NOW EXPLAINING</span><strong>Agent {agents[activeIndex].number} · {agents[activeIndex].title}</strong></div><p>{agents[activeIndex].detail}</p><div className="playback-explain__contract"><span><b>Receives</b>{agents[activeIndex].input}</span><span className="playback-explain__arrow">→</span><span><b>Passes forward</b>{agents[activeIndex].output}</span></div></div>
          <div className="feedback-loop"><span className="feedback-loop__line" /> <strong>re-check loop</strong> Agent 12 can send a failed novelty/evidence review back to Agent 10; it is a controlled correction path, not a hidden shortcut.</div>
          <div className="map-caption"><span className="caption-dot caption-dot--filled" /> each station passes its output artifact to the next station <span className="caption-dot caption-dot--outline" /> click any station to inspect the full contract</div>
        </div>

        <aside className="agent-detail-card">
          <div className="agent-detail-card__top"><span className="detail-index" style={{ color: selected.color }}>AGENT {selected.number}</span><span className="detail-phase" style={{ color: selected.color, borderColor: selected.color }}>{selected.phase}</span></div>
          <h2>Skill &amp; execution context</h2>
          <p className="agent-detail-card__description agent-detail-card__description--compact">The narrative above explains the role. This panel shows the reusable procedural context loaded around that role.</p>
          <div className="runtime-panel"><span className="detail-label">Runtime type</span><strong className={`runtime-panel__value runtime-panel__value--${deterministicAgents.has(selected.id) ? "deterministic" : "llm"}`}>{runtimeType(selected.id)}</strong><p>{deterministicAgents.has(selected.id) ? "This stage reads persisted upstream artifacts and computes graph outputs locally without a new model call." : "This stage invokes Codex with the agent contract, selected skills and compact upstream artifacts."}</p></div>
          <div className="detail-example"><span className="detail-label">Concrete example</span><p>{agentExamples[selected.id]}</p></div>
          <div className="detail-section"><span className="detail-label">Loaded skills</span>{selected.skills.length > 0 ? <div className="skill-list">{selected.skills.map((skill) => { const info = skillInfo[skill]; return <article className="skill-card" key={skill}><div className="skill-card__header"><strong>{info?.name ?? skill}</strong><code>{skill}</code></div><p>{info?.purpose ?? "Reusable procedural instruction module."}</p><div className="skill-card__meta"><span><b>Loaded</b>{info?.loaded ?? "Before this agent"}</span><span><b>Produces</b>{info?.output ?? "Structured evidence"}</span></div></article>; })}</div> : <p className="muted">No dedicated skill module. This agent uses its contract and upstream artifacts directly.</p>}</div>
          <div className="detail-section"><span className="detail-label">Why it exists</span><p className="muted">Each hand-off is persisted before the next agent starts, making failures inspectable and the final graph reproducible.</p></div>
        </aside>
      </section>

      <section className="skill-atlas card">
        <div className="section-heading"><div><p className="eyebrow">Reusable context modules</p><h2>Skill atlas</h2></div><span className="muted">Skills are loaded at dispatch time, not hidden in a prompt.</span></div>
        <div className="skill-atlas__grid">{skillAtlas.map(({ id, info, users }) => <article className="skill-atlas__card" key={id}><div className="skill-atlas__title"><span className="skill-atlas__icon">*</span><h3>{info.name}</h3></div><code>{id}</code><p>{info.purpose}</p><div className="skill-atlas__footer"><span><b>Loaded</b>{info.loaded}</span><span><b>Used by</b>Agents {users.join(", ")}</span></div></article>)}</div>
      </section>

      <section className="architecture-story card">
        <div><p className="eyebrow">The story to tell</p><h2>Evidence is not a hypothesis</h2><p className="muted">The system deliberately separates discovery, graph construction, novelty classification, review and experiment design. The orange gate is where a plausible mechanism must earn the right to become a hypothesis.</p></div>
        <div className="story-steps"><span><b>01</b> collect and verify</span><span><b>02</b> structure the graph</span><span><b>03</b> challenge novelty</span><span><b>04</b> design the test</span></div>
      </section>
    </div>
  );
}
