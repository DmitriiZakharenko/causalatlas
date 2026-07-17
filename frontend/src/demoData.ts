export const fallbackDemoSteps = [
  { number: "00", title: "Orchestrator", description: "Sequences agents, loads skills and persists checkpoints.", metrics: ["13 agents scheduled"], artifact: "run_events" },
  { number: "01", title: "Canonical baseline", description: "Anchors IPF + IL11 in established pathway knowledge.", metrics: ["4 database sources"], artifact: "canonical_baseline.json" },
  { number: "02", title: "Literature retrieval", description: "Builds mechanism-specific PubMed evidence chains.", metrics: ["query strategies", "unique papers"], artifact: "publications_raw.json" },
  { number: "03", title: "Publication verification", description: "Checks publication identity and relevance.", metrics: ["verified", "rejected"], artifact: "verification_report.json" },
  { number: "04", title: "Quality filter", description: "Ranks evidence and flags translation uncertainty.", metrics: ["evidence levels"], artifact: "quality_scores.json" },
  { number: "05", title: "Mechanistic extraction", description: "Converts explicit findings into causal edges.", metrics: ["extracted edges"], artifact: "mechanisms_extracted.json" },
  { number: "06–09", title: "Graph stages", description: "Builds, analyzes and stress-tests the causal graph.", metrics: ["nodes", "edges", "loops"], artifact: "knowledge_graph.json" },
  { number: "10", title: "Novelty verification", description: "Runs the A–E novelty gate.", metrics: ["audits", "D/E candidates"], artifact: "novelty_audit.json" },
  { number: "11–12", title: "Hypothesis + peer review", description: "Generates candidates and tries to falsify them.", metrics: ["hypotheses", "reviews"], artifact: "peer_review.json" },
  { number: "13", title: "Experiment design", description: "Turns surviving candidates into a validation plan.", metrics: ["experiment designs"], artifact: "experiment_design.json" },
] as const;
