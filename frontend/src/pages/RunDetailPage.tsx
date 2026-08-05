import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { subscribeToRun } from "../api/sse";
import type { Decision, PipelineEvent, RunStatusResponse } from "../api/types";
import StatusBadge from "../components/StatusBadge";

interface TimelineEntry {
  key: string;
  at: number;
  event: PipelineEvent;
}

function describeEvent(event: PipelineEvent): string {
  switch (event.type) {
    case "skill_loaded":
      return `Loaded skill "${event.skill}"`;
    case "agent_started":
      return `Agent started: ${event.agent}`;
    case "agent_completed":
      return `Agent completed: ${event.agent}`;
    case "run_completed":
      return `Run completed — ${event.total_tokens !== undefined ? `${event.total_tokens.toLocaleString()} tokens` : "token usage not reported"}${event.cost_usd !== undefined && event.cost_usd !== null ? ` · $${event.cost_usd.toFixed(4)}` : " · subscription cost not reported"}`;
    case "run_failed":
      return `Run failed — ${event.reason}`;
    case "run_cancelled":
      return `Run cancelled — ${event.reason}`;
    case "run_paused":
      return `Paused at ${event.agent ?? "unknown agent"} — ${event.reason}`;
    default:
      return JSON.stringify(event);
  }
}

export default function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const [status, setStatus] = useState<RunStatusResponse | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [decisionNote, setDecisionNote] = useState("");
  const [submittingDecision, setSubmittingDecision] = useState(false);
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);

  const terminalUsage = timeline
    .map((entry) => entry.event)
    .find((event): event is Extract<PipelineEvent, { type: "run_completed" }> => event.type === "run_completed");

  const refreshStatus = useCallback(() => {
    if (!runId) return;
    api
      .getRunStatus(runId)
      .then(setStatus)
      .catch((err) => setStatusError(err instanceof ApiError ? `${err.status}: ${err.message}` : String(err)));
  }, [runId]);

  useEffect(() => {
    refreshStatus();
  }, [refreshStatus]);

  useEffect(() => {
    if (!runId) return;
    const unsubscribe = subscribeToRun(runId, (event) => {
      const atMs = event.created_at ? event.created_at * 1000 : Date.now();
      const key = event.seq !== undefined ? `seq-${event.seq}` : `${atMs}-${event.type}`;
      setTimeline((prev) => {
        if (prev.some((entry) => entry.key === key)) return prev;
        return [...prev, { key, at: atMs, event }];
      });
      if (event.type !== "skill_loaded") refreshStatus();
    });
    return unsubscribe;
  }, [runId, refreshStatus]);

  const submitDecision = async (decision: Decision) => {
    if (!runId) return;
    setSubmittingDecision(true);
    setDecisionError(null);
    try {
      await api.submitDecision(runId, decision, decisionNote.trim() || undefined);
      setDecisionNote("");
      refreshStatus();
    } catch (err) {
      setDecisionError(err instanceof ApiError ? `${err.status}: ${err.message}` : String(err));
    } finally {
      setSubmittingDecision(false);
    }
  };

  const cancelRun = async () => {
    if (!runId) return;
    setCancelling(true);
    try {
      await api.cancelRun(runId);
      refreshStatus();
    } catch (err) {
      setStatusError(err instanceof ApiError ? `${err.status}: ${err.message}` : String(err));
    } finally {
      setCancelling(false);
    }
  };

  if (!runId) return <p className="error-text">No run id in URL.</p>;

  return (
    <div className="page">
      <section className="card">
        <div className="run-header">
          <div>
            <h1>
              {status?.disease ?? runId} {status?.gene ? `· ${status.gene}` : ""}
            </h1>
            <p className="muted">
              run_id: <code>{runId}</code>
            </p>
          </div>
          {status && <StatusBadge status={status.status} />}
        </div>
        {status && ["pending", "running", "paused"].includes(status.status) && (
          <button className="button button--danger run-cancel-button" disabled={cancelling} onClick={cancelRun}>
            {cancelling ? "Stopping…" : "Stop run"}
          </button>
        )}

        {statusError && <p className="error-text">{statusError}</p>}
        {status?.error && status.status === "failed" && (
          <pre className="error-text">{status.error}</pre>
        )}

        {status?.status === "running" && (
          <p className="muted">
            Run is in progress. Older failures in the timeline are from previous attempts — not
            necessarily the current one. Avoid refreshing this page while agents are working.
          </p>
        )}

        {status?.status === "paused" && (
          <div className="pause-panel">
            <h3>Awaiting your decision — paused at {status.current_agent ?? "unknown agent"}</h3>
            <textarea
              placeholder="Optional note explaining your decision…"
              value={decisionNote}
              onChange={(e) => setDecisionNote(e.target.value)}
            />
            <div className="pause-panel__actions">
              <button
                className="button button--primary"
                disabled={submittingDecision}
                onClick={() => submitDecision("approve")}
              >
                Approve
              </button>
              <button className="button" disabled={submittingDecision} onClick={() => submitDecision("edit")}>
                Approve with edit note
              </button>
              <button
                className="button button--danger"
                disabled={submittingDecision}
                onClick={() => submitDecision("reject")}
              >
                Reject
              </button>
            </div>
            {decisionError && <p className="error-text">{decisionError}</p>}
          </div>
        )}
      </section>

      {status?.evidence_summary && (
        <section className="run-quality-strip">
          <div><span>Pipeline execution</span><strong>{status.evidence_summary.execution.complete ? "completed" : status.evidence_summary.execution.status}</strong></div>
          <div><span>Evidence quality</span><strong className={status.evidence_summary.evidence.quality === "degraded" ? "run-quality-strip__warn" : ""}>{status.evidence_summary.evidence.quality}</strong></div>
          <div><span>Hypothesis readiness</span><strong className={status.evidence_summary.hypotheses.ready ? "run-quality-strip__ok" : "run-quality-strip__warn"}>{status.evidence_summary.hypotheses.ready ? "ready" : "not ready"}</strong></div>
        </section>
      )}

      {terminalUsage && (
        <section className="run-usage-strip" aria-label="Run usage">
          <div><span>Input tokens</span><strong>{terminalUsage.input_tokens?.toLocaleString() ?? "Not reported"}</strong></div>
          <div><span>Output tokens</span><strong>{terminalUsage.output_tokens?.toLocaleString() ?? "Not reported"}</strong></div>
          <div><span>Total tokens</span><strong>{terminalUsage.total_tokens?.toLocaleString() ?? "Not reported"}</strong></div>
          <div><span>Provider cost</span><strong>{terminalUsage.cost_usd !== undefined && terminalUsage.cost_usd !== null ? `$${terminalUsage.cost_usd.toFixed(4)}` : "Not reported"}</strong></div>
        </section>
      )}

      <section className="card">
        <h2>Live progress</h2>
        {timeline.length === 0 && <p className="muted">Waiting for the first event…</p>}
        <ol className="timeline">
          {timeline.map((entry) => (
            <li key={entry.key} className={`timeline__item timeline__item--${entry.event.type}`}>
              <span className="timeline__time">{new Date(entry.at).toLocaleTimeString()}</span>
              <span className="timeline__desc">{describeEvent(entry.event)}</span>
            </li>
          ))}
        </ol>
      </section>

      {status && status.interventions.length > 0 && (
        <section className="card">
          <h2>Human intervention audit trail</h2>
          <table className="table">
            <thead>
              <tr>
                <th>Agent</th>
                <th>Decision</th>
                <th>Note</th>
                <th>When</th>
              </tr>
            </thead>
            <tbody>
              {status.interventions.map((iv) => (
                <tr key={iv.id}>
                  <td>{iv.agent_name}</td>
                  <td>{iv.decision}</td>
                  <td>{iv.note ?? "—"}</td>
                  <td>{new Date(iv.created_at * 1000).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
