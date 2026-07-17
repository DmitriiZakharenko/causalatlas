import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { EvidenceSummary, RunSummary } from "../api/types";

const metricDefinitions: [keyof EvidenceSummary["evidence"], string, string][] = [
  ["verified_papers", "Verified papers", "Publications that passed PMID, relevance, and mechanistic-evidence checks."],
  ["rejected_papers", "Rejected papers", "Search results excluded because of weak relevance, quality, or invalid metadata."],
  ["independent_sources", "Independent sources", "Separate sources supporting the mechanism. More independent sources reduce single-paper bias."],
  ["contradictions", "Contradictions", "Conflicting directions or conclusions for the same graph relationship. These require review rather than being hidden."],
  ["fallback_count", "Fallback files", "Artifacts created through a fallback path after an incomplete agent response. This signals degraded evidence quality."],
];

const noveltyGroups = [
  ["A", "Established consensus", "A well-supported consensus mechanism; it is not a new discovery.", "Not eligible as a novel hypothesis."],
  ["B", "Previously published", "The same or practically identical hypothesis has already been published.", "Displayed as a known result and stopped at the novelty gate."],
  ["C", "Conflicting literature", "The literature contains substantial conflicts about the mechanism's direction or causality.", "Requires additional review; not automatically treated as novel."],
  ["D", "Partially established", "Part of the chain is supported, but the complete target-to-mechanism-to-disease link is not established.", "May become a candidate when evidence and independent sources are sufficient."],
  ["E", "Potentially novel", "The link appears novel in the searched literature but requires strict independent verification.", "Primary group for new-hypothesis generation, not a guarantee of acceptance."],
  ["RESTATED", "Restated finding", "The wording paraphrases a known result without adding a new causal step.", "Rejected as a restatement even if biologically plausible."],
];

function candidateStatement(statement: string | null): string {
  const value = statement?.trim();
  if (!value) return "No concrete mechanistic hypothesis was persisted for this candidate.";
  if (/^mechanistic gap candidates in /i.test(value)) {
    return `No concrete mechanistic hypothesis was persisted. Candidate label: ${value}`;
  }
  return value;
}

function candidateDisposition(classification: string | null, eligible: boolean): string {
  if (eligible) return "Eligible for hypothesis generation";
  const code = String(classification ?? "").toUpperCase();
  if (code === "A") return "Established consensus; not eligible";
  if (code === "B") return "Previously published; not eligible";
  if (code === "C") return "Conflicting literature; held for review";
  if (code === "RESTATED") return "Restated finding; not eligible";
  return "Not eligible for hypothesis generation";
}

export default function EvidenceDashboardPage() {
  const [searchParams] = useSearchParams();
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [summary, setSummary] = useState<EvidenceSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listRuns().then((response) => {
      const visibleRuns = response.runs.filter((run) => run.status !== "failed" && run.status !== "cancelled");
      setRuns(visibleRuns);
      const requestedRun = searchParams.get("run");
      const initialRun = visibleRuns.find((run) => run.run_id === requestedRun) ?? visibleRuns[0];
      if (initialRun) setSelectedId(initialRun.run_id);
    }).catch((err) => setError(err instanceof ApiError ? `${err.status}: ${err.message}` : String(err)));
  }, [searchParams]);

  useEffect(() => {
    if (!selectedId) return;
    api.getEvidence(selectedId).then(setSummary).catch((err) => setError(err instanceof ApiError ? `${err.status}: ${err.message}` : String(err)));
  }, [selectedId]);

  const selected = runs.find((run) => run.run_id === selectedId);

  return (
    <div className="page page--wide">
      <section className="card evidence-header">
        <div><p className="eyebrow">Evidence quality / run audit</p><h1>Evidence dashboard</h1><p className="muted">Pipeline execution and scientific readiness are reported separately. A completed run can still be degraded or produce zero ready hypotheses.</p></div>
        <label className="evidence-picker">Run<select value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>{runs.map((run) => <option key={run.run_id} value={run.run_id}>{run.disease} · {run.gene ?? "no gene"} · {run.run_id}</option>)}</select></label>
      </section>
      {error && <p className="error-text">{error}</p>}
      {summary && selected && <>
        <section className="evidence-status-grid">
          <div className="card evidence-status-card"><span>Pipeline execution</span><strong className={`evidence-status evidence-status--${summary.execution.complete ? "complete" : "running"}`}>{summary.execution.complete ? "completed" : summary.execution.status}</strong><small>Current agent: {summary.execution.current_agent ?? "none"}</small></div>
          <div className="card evidence-status-card"><span>Evidence quality</span><strong className={`evidence-status evidence-status--${summary.evidence.quality}`}>{summary.evidence.quality}</strong><small>{summary.evidence.fallback_count} fallback file(s), {summary.evidence.verified_papers} verified papers</small></div>
          <div className="card evidence-status-card"><span>Hypothesis readiness</span><strong className={`evidence-status evidence-status--${summary.hypotheses.ready ? "complete" : "degraded"}`}>{summary.hypotheses.ready ? "ready" : "not ready"}</strong><small>{summary.hypotheses.accepted} accepted · {summary.hypotheses.d_e_candidates} D/E candidates</small></div>
        </section>
        <section className="card evidence-guide"><div><p className="eyebrow">Reading the dashboard</p><h2>How to read the metrics</h2><p className="muted">These metrics describe evidence-corpus quality and novelty-gate outcomes. They are not the number of new hypotheses: a paper can be verified while the candidate is still known or restated.</p></div><div className="evidence-guide__metric-list">{metricDefinitions.map(([key, label, description]) => <div key={key}><strong>{label}</strong><span>{description}</span></div>)}<div><strong>Generated / accepted</strong><span>Generated means candidates created by Agent 11. Accepted means candidates that passed novelty and peer review. Only accepted candidates are ready for experiment design.</span></div></div></section>
        <section className="evidence-metrics-grid">{metricDefinitions.map(([key, label, description]) => <div className="card evidence-metric" key={key} title={description}><span>{label}</span><strong>{summary.evidence[key] as number}</strong></div>)}<div className="card evidence-metric" title="Candidates generated by Agent 11 from D/E evidence."><span>Generated hypotheses</span><strong>{summary.hypotheses.generated}</strong></div></section>
        {(summary.hypothesis_records ?? []).length > 0 && <section className="card"><div className="section-heading"><div><p className="eyebrow">Agent 11 output</p><h2>Generated hypothesis</h2></div><span className="muted">Read from this run's session artifact</span></div>{summary.hypothesis_records?.map((hypothesis, index) => <article className="hypothesis-record" key={`${hypothesis.id ?? "hypothesis"}-${index}`}><div className="hypothesis-record__header"><strong>{hypothesis.id ?? `Hypothesis ${index + 1}`}</strong><span>{hypothesis.class ?? "Class not recorded"}</span></div>{hypothesis.source_gap && <p><b>Evidence gap:</b> {hypothesis.source_gap}</p>}{hypothesis.specific_prediction && <p><b>Specific prediction:</b> {hypothesis.specific_prediction}</p>}{hypothesis.falsification && <p><b>Falsification:</b> {hypothesis.falsification}</p>}</article>)}</section>}
        {summary.experiment_design && (summary.experiment_design.experiments.length > 0 || summary.experiment_design.status) && <section className="card"><div className="section-heading"><div><p className="eyebrow">Agent 13 output</p><h2>Experiment design</h2></div><span className="muted">{summary.experiment_design.status ?? "Design recorded"}{summary.experiment_design.hypothesis_id ? ` · ${summary.experiment_design.hypothesis_id}` : ""}</span></div>{summary.experiment_design.model_system && <p><b>Model system:</b> {summary.experiment_design.model_system}</p>}{summary.experiment_design.experiments.map((experiment, index) => <article className="experiment-record" key={experiment.id ?? `experiment-${index}`}><h3>{experiment.id ?? `Experiment ${index + 1}`}</h3><p><b>Method:</b> {experiment.method}</p><p><b>Predicted outcome:</b> {experiment.predicted_outcome}</p><p><b>Falsification criterion:</b> {experiment.falsification_criterion}</p></article>)}{summary.experiment_design.primary_readout && <p><b>Primary readout:</b> {summary.experiment_design.primary_readout}</p>}</section>}
        <section className="card"><div className="section-heading"><div><p className="eyebrow">Mechanism-specific retrieval</p><h2>Papers per mechanism chain</h2></div><span className="muted">Queries: {summary.evidence.papers_per_mechanism_chain.length}</span></div><table className="table evidence-table"><thead><tr><th>Strategy</th><th>Papers</th><th>Query</th></tr></thead><tbody>{summary.evidence.papers_per_mechanism_chain.map((chain, index) => <tr key={`${chain.strategy}-${index}`}><td><strong>{chain.strategy}</strong></td><td>{chain.papers}</td><td>{chain.query}</td></tr>)}</tbody></table></section>
        <section className="card"><div className="section-heading"><div><p className="eyebrow">Novelty gate output</p><h2>All candidate classifications</h2></div><span className="muted">Accepted and rejected candidates are both shown</span></div><table className="table evidence-table"><thead><tr><th>Candidate</th><th>Class</th><th>Disposition</th><th>Hypothesis statement and gate decision</th></tr></thead><tbody>{(summary.novelty_audits ?? []).map((audit, index) => <tr key={`${audit.hypothesis_id ?? "candidate"}-${index}`}><td><strong>{audit.hypothesis_id ?? `Candidate ${index + 1}`}</strong></td><td><span className={`novelty-class novelty-class--${String(audit.classification ?? "unknown").toLowerCase()}`}>{audit.classification ?? "unknown"}</span></td><td>{candidateDisposition(audit.classification, audit.eligible)}</td><td><div className="novelty-statement"><strong>{candidateStatement(audit.statement)}</strong><span>{audit.action ?? "No gate decision recorded."}</span></div></td></tr>)}</tbody></table>{(!summary.novelty_audits || summary.novelty_audits.length === 0) && <p className="muted">No normalized novelty records found in this run.</p>}</section>
        <section className="card"><div className="section-heading"><div><p className="eyebrow">Stored audit corpus</p><h2>Novelty groups across runs</h2></div><span className="muted">Historical and current graph audit files</span></div><p className="muted evidence-legend-intro">The classification shows what the literature search supports. `D` and `E` are candidates for new hypotheses, not automatically accepted hypotheses.</p><div className="novelty-catalog-grid">{noveltyGroups.map(([code, title, description, consequence]) => <div key={code}><div className="novelty-catalog-grid__top"><span className={`novelty-class novelty-class--${code.toLowerCase()}`}>{code}</span><strong>{(summary.novelty_catalog ?? []).filter((item) => item.classification === code).length}</strong></div><b>{title}</b><small>{description}</small><small className="novelty-consequence">{consequence}</small></div>)}</div></section>
        <section className="card evidence-foot"><div><h2>What this means</h2><p className="muted">{summary.execution.complete ? "The orchestration reached its terminal state." : "The orchestration is still running."} {summary.evidence.quality === "degraded" ? "Evidence quality is degraded, so hypothesis readiness is deliberately blocked." : "Evidence passed the basic completeness checks."}</p></div><div><span className="detail-label">Search controls</span><p className="muted">{summary.checkpoints?.length ?? 0} checkpoint(s) · {summary.evidence.fallback_count} fallback file(s)</p><p className="muted">{summary.artifacts.join(" · ")}</p></div></section>
      </>}
    </div>
  );
}
