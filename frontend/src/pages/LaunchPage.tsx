import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { AutonomyLevel, RunSummary } from "../api/types";
import StatusBadge from "../components/StatusBadge";

const AUTONOMY_OPTIONS: { value: AutonomyLevel; label: string; description: string }[] = [
  {
    value: "let_it_rip",
    label: "Let it rip",
    description: "Runs all 13 agents end to end with no pause points.",
  },
  {
    value: "supervised",
    label: "Supervised",
    description: "Pauses before Agent 10's novelty classification and before Agent 13, for human sign-off.",
  },
  {
    value: "autocomplete",
    label: "Autocomplete (max caution)",
    description: "Pauses after every single agent for a human decision.",
  },
];

export default function LaunchPage() {
  const navigate = useNavigate();
  const [disease, setDisease] = useState("");
  const [gene, setGene] = useState("");
  const [autonomyLevel, setAutonomyLevel] = useState<AutonomyLevel>("let_it_rip");
  const [devRetmax, setDevRetmax] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [runsError, setRunsError] = useState<string | null>(null);
  const [provider, setProvider] = useState<string | null>(null);

  const loadRuns = () => {
    api
      .listRuns()
      .then((r) => setRuns(r.runs))
      .catch((err) => setRunsError(err instanceof ApiError ? `${err.status}: ${err.message}` : String(err)));
  };

  useEffect(() => {
    loadRuns();
    api.health().then((health) => setProvider(health.llm_provider)).catch(() => undefined);
    const interval = setInterval(loadRuns, 5000);
    return () => clearInterval(interval);
  }, []);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!disease.trim()) {
      setSubmitError("Disease is required.");
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      const result = await api.startRun({
        disease: disease.trim(),
        gene: gene.trim() || undefined,
        autonomy_level: autonomyLevel,
        dev_pubmed_retmax: devRetmax.trim() ? Number(devRetmax.trim()) : undefined,
      });
      navigate(`/runs/${result.run_id}`);
    } catch (err) {
      setSubmitError(err instanceof ApiError ? `${err.status}: ${err.message}` : String(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="page">
      <section className="card">
        <h1>Launch a mechanistic-hypothesis run</h1>
        <p className="muted">
          Runs a live {provider ?? "configured"} pipeline sequentially, per{" "}
          <code>agents/agent00_orchestrator/AGENTS.md</code>. Nothing here is a stub or mock.
        </p>

        <aside className="provider-help" aria-label="LLM provider configuration">
          <div className="provider-help__header">
            <div>
              <span className="eyebrow">Backend provider</span>
              <h2>{provider === "offline" ? "Offline snapshots" : provider ? `${provider} CLI connected` : "Checking provider…"}</h2>
            </div>
            <span className="provider-help__status">{provider ?? "pending"}</span>
          </div>
          <p className="muted">The browser does not choose or store model credentials. The backend selects the locally authenticated CLI through <code>LLM_PROVIDER</code>.</p>
          <details>
            <summary>Switch between Claude Code and Codex CLI</summary>
            <ol className="provider-help__steps">
              <li>Stop the backend with <code>Ctrl+C</code>.</li>
              <li>Authenticate the CLI you want to use: <code>claude login</code> or <code>codex login</code>.</li>
              <li>In the repository <code>.env</code>, set <code>LLM_PROVIDER=codex</code> or <code>LLM_PROVIDER=claude</code>.</li>
              <li>Start the backend again. The provider badge above will update.</li>
            </ol>
            <pre className="provider-help__code">{`# Codex\ncodex login\nLLM_PROVIDER=codex\n\n# Claude Code\nclaude login\nLLM_PROVIDER=claude`}</pre>
            <p className="muted">Never paste API keys into this page, the frontend or the repository. Authentication stays in the CLI's user-level configuration.</p>
          </details>
        </aside>

        <form onSubmit={onSubmit} className="form">
          <div className="form__row">
            <label>
              Disease / target *
              <input
                value={disease}
                onChange={(e) => setDisease(e.target.value)}
                placeholder="e.g. psoriasis"
                required
              />
            </label>
            <label>
              Gene (optional)
              <input value={gene} onChange={(e) => setGene(e.target.value)} placeholder="e.g. IL23A" />
            </label>
          </div>

          <fieldset className="form__autonomy">
            <legend>Autonomy level</legend>
            {AUTONOMY_OPTIONS.map((opt) => (
              <label key={opt.value} className="form__radio">
                <input
                  type="radio"
                  name="autonomy_level"
                  value={opt.value}
                  checked={autonomyLevel === opt.value}
                  onChange={() => setAutonomyLevel(opt.value)}
                />
                <span>
                  <strong>{opt.label}</strong>
                  <span className="muted"> — {opt.description}</span>
                </span>
              </label>
            ))}
          </fieldset>

          <details className="form__advanced">
            <summary>Dev-loop cost knob (advanced)</summary>
            <label>
              Override Agent 2's PubMed retmax per year-band (default 200) — use a small number
              (e.g. 25) to validate orchestration cheaply before a full-cost run.
              <input
                type="number"
                min={1}
                value={devRetmax}
                onChange={(e) => setDevRetmax(e.target.value)}
                placeholder="leave blank for a real/demo run"
              />
            </label>
          </details>

          {submitError && <p className="error-text">{submitError}</p>}

          <button type="submit" className="button button--primary" disabled={submitting}>
            {submitting ? "Starting…" : `Run live ${provider ?? "pipeline"} analysis`}
          </button>
        </form>
      </section>

      <section className="card">
        <h2>Runs</h2>
        {runsError && <p className="error-text">{runsError}</p>}
        {!runsError && runs === null && <p className="muted">Loading…</p>}
        {runs !== null && runs.length === 0 && <p className="muted">No runs yet — launch one above.</p>}
        {runs !== null && runs.length > 0 && (
          <>
            {runs.every((r) => r.status !== "completed") && <p className="muted">No successful recorded analyses yet.</p>}
            <div className="recorded-run-grid" aria-label="Successful recorded analyses">
              {runs.filter((r) => r.status === "completed").map((r) => (
                <article key={`card-${r.run_id}`} className="recorded-run-card">
                  <button type="button" className="recorded-run-card__main" onClick={() => navigate(`/runs/${r.run_id}`)}>
                    <span className="eyebrow">Recorded analysis</span>
                    <strong>{r.disease} · {r.gene ?? "target not specified"}</strong>
                    <span className="muted">{r.status} · {r.current_agent ?? "pipeline complete"}</span>
                  </button>
                  <div className="recorded-run-card__actions">
                    <button type="button" className="button button--primary" onClick={() => navigate(`/runs/${r.run_id}`)}>Open run</button>
                    <button type="button" className="button" onClick={() => navigate(`/graphs?disease=${encodeURIComponent(r.disease.toLowerCase().replaceAll(" ", "_"))}`)}>Graph</button>
                    <button type="button" className="button" onClick={() => navigate(`/evidence?run=${encodeURIComponent(r.run_id)}`)}>Evidence</button>
                  </div>
                </article>
              ))}
            </div>
            <table className="table">
            <thead>
              <tr>
                <th>Disease</th>
                <th>Gene</th>
                <th>Autonomy</th>
                <th>Status</th>
                <th>Current agent</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.run_id} onClick={() => navigate(`/runs/${r.run_id}`)} className="table__row--clickable">
                  <td>{r.disease}</td>
                  <td>{r.gene ?? "—"}</td>
                  <td>{r.autonomy_level}</td>
                  <td>
                    <StatusBadge status={r.status} />
                  </td>
                  <td>{r.current_agent ?? "—"}</td>
                  <td>
                    <a
                      href={`/runs/${r.run_id}`}
                      onClick={(e) => {
                        e.preventDefault();
                        navigate(`/runs/${r.run_id}`);
                      }}
                    >
                      View →
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
            </table>
          </>
        )}
      </section>
    </div>
  );
}
