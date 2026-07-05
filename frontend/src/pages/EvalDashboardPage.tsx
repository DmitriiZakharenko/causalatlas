import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { EvalDashboardMetrics, EvalScore } from "../api/types";

function pct(x: number | null): string {
  if (x === null) return "—";
  return `${(x * 100).toFixed(0)}%`;
}

const OUTCOME_LABELS: Record<string, string> = {
  confirmed_false_positive_historical: "Confirmed false positive (historical)",
  correctly_rejected: "Correctly rejected",
  accepted_pending_validation: "Accepted, pending validation",
  judge_agrees: "Live judge agrees",
  judge_disagrees: "Live judge disagrees",
};

export default function EvalDashboardPage() {
  const [metrics, setMetrics] = useState<EvalDashboardMetrics | null>(null);
  const [scores, setScores] = useState<EvalScore[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [backfilling, setBackfilling] = useState(false);

  const load = () => {
    Promise.all([api.getEvalDashboard(), api.getEvalScores()])
      .then(([m, s]) => {
        setMetrics(m);
        setScores(s.scores);
      })
      .catch((err) => setError(err instanceof ApiError ? `${err.status}: ${err.message}` : String(err)));
  };

  useEffect(load, []);

  const runBackfill = async () => {
    setBackfilling(true);
    setError(null);
    try {
      await api.runEvalBackfill();
      load();
    } catch (err) {
      setError(err instanceof ApiError ? `${err.status}: ${err.message}` : String(err));
    } finally {
      setBackfilling(false);
    }
  };

  return (
    <div className="page">
      <section className="card">
        <div className="run-header">
          <div>
            <h1>Reliability dashboard</h1>
            <p className="muted">
              The eval flywheel: real historical backfill from Sessions 001-003 (see{" "}
              <code>eval/historical_backfill.json</code>) plus, for future runs, an independent
              blind live judge (<code>agent14_eval_judge</code>). Nothing on this page is
              fabricated — every number traces to a real file or a real model call.
            </p>
          </div>
          <button className="button" onClick={runBackfill} disabled={backfilling}>
            {backfilling ? "Recomputing…" : "Recompute historical backfill"}
          </button>
        </div>
        {error && <p className="error-text">{error}</p>}
      </section>

      {metrics && (
        <section className="metrics-grid">
          <div className="card metric-card">
            <span className="metric-card__label">Historical gate retroactive catch rate</span>
            <span className="metric-card__value">{pct(metrics.historical_gate_retroactive_catch_rate)}</span>
            <span className="muted">
              Fraction of known historical false positives (H1/H2, Session 001) that the CURRENT
              mandatory novelty gate would have caught, per their real re-audit ground truth.
            </span>
          </div>
          <div className="card metric-card">
            <span className="metric-card__label">Live judge agreement rate</span>
            <span className="metric-card__value">{pct(metrics.live_judge_agreement_rate)}</span>
            <span className="muted">No live judge runs yet — populates once a run is audited.</span>
          </div>
          <div className="card metric-card">
            <span className="metric-card__label">Total scored</span>
            <span className="metric-card__value">{metrics.total_scored}</span>
            <span className="muted">Sessions covered: {metrics.sessions_covered.join(", ") || "none"}</span>
          </div>
        </section>
      )}

      {metrics && (
        <section className="card">
          <h2>Outcome breakdown</h2>
          <table className="table">
            <thead>
              <tr>
                <th>Outcome</th>
                <th>Count</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(metrics.outcome_counts).map(([outcome, count]) => (
                <tr key={outcome}>
                  <td>{OUTCOME_LABELS[outcome] ?? outcome}</td>
                  <td>{count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <section className="card">
        <h2>Scored hypotheses</h2>
        {scores === null && <p className="muted">Loading…</p>}
        {scores !== null && scores.length === 0 && (
          <p className="muted">No scores yet — click "Recompute historical backfill" above.</p>
        )}
        {scores !== null && scores.length > 0 && (
          <table className="table">
            <thead>
              <tr>
                <th>Session / run</th>
                <th>Hypothesis</th>
                <th>Outcome</th>
                <th>Original label</th>
                <th>Ground truth</th>
                <th>Reasoning</th>
              </tr>
            </thead>
            <tbody>
              {scores.map((s) => (
                <tr key={s.id}>
                  <td>{s.session_id}</td>
                  <td>{s.hypothesis_id ?? "—"}</td>
                  <td>
                    <span className={`badge badge--outcome-${s.outcome}`}>
                      {OUTCOME_LABELS[s.outcome] ?? s.outcome}
                    </span>
                  </td>
                  <td>{s.original_label ?? "—"}</td>
                  <td>{s.ground_truth ?? "—"}</td>
                  <td className="table__reasoning">{s.reasoning ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
