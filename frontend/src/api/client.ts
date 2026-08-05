import type {
  AutonomyLevel,
  EvalDashboardMetrics,
  EvalScore,
  GraphResponse,
  GraphSummary,
  JudgeVerdict,
  RunStatusResponse,
  RunSummary,
  StartRunResponse,
  AnalysisTarget,
  EvidenceSummary,
} from "./types";
import { OFFLINE_EVIDENCE, OFFLINE_GRAPHS, OFFLINE_RUN, OFFLINE_RUNS } from "../offlineData";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const queryParams = new URLSearchParams(window.location.search);
const liveQueryEnabled = queryParams.has("live");
const offlineQueryEnabled = queryParams.has("offline");
const standaloneEntry = window.location.pathname.endsWith("/demo.html");
// The main entry is live by default. The standalone entry is always offline;
// the main app can opt into embedded snapshots with `?offline=1`.
const OFFLINE_MODE = !liveQueryEnabled && (standaloneEntry || offlineQueryEnabled);

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new ApiError(res.status, body || res.statusText);
  }
  return res.json() as Promise<T>;
}

function qs(params: Record<string, string | undefined>): string {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined) as [string, string][];
  if (entries.length === 0) return "";
  return `?${new URLSearchParams(entries).toString()}`;
}

export const api = {
  health: () =>
    OFFLINE_MODE
      ? Promise.resolve({ status: "ok", service: "causalatlas-offline", phase: "recorded snapshot", llm_provider: "offline", pipeline_agents: [], timestamp: new Date().toISOString() })
      : request<{ status: string; service: string; phase: string; llm_provider: string; pipeline_agents: string[]; timestamp: string }>("/api/health"),

  // --- Pipeline runs (Phase 2/3) ---------------------------------------
  startRun: (payload: {
    disease: string;
    gene?: string;
    target?: AnalysisTarget;
    autonomy_level?: AutonomyLevel;
    dev_pubmed_retmax?: number;
  }) =>
    OFFLINE_MODE ? Promise.reject(new ApiError(503, "Offline mode is read-only; start the backend to launch a new run.")) : request<StartRunResponse>("/api/pipeline/run", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listRuns: () => OFFLINE_MODE ? Promise.resolve({ runs: OFFLINE_RUNS }) : request<{ runs: RunSummary[] }>("/api/pipeline/runs"),

  getRunStatus: (runId: string) => OFFLINE_MODE ? Promise.resolve({ ...(OFFLINE_RUNS.find((run) => run.run_id === runId) ?? OFFLINE_RUN), interventions: [] }) : request<RunStatusResponse>(`/api/pipeline/${runId}/status`),

  getEvidence: (runId: string) => OFFLINE_MODE ? Promise.resolve({ ...OFFLINE_EVIDENCE, run_id: runId }) : request<EvidenceSummary>(`/api/evidence/${runId}`),

  getDemoReplay: () => OFFLINE_MODE ? Promise.resolve(OFFLINE_EVIDENCE) : request<EvidenceSummary>("/api/demo/replay"),

  submitDecision: (runId: string, decision: "approve" | "reject" | "edit", note?: string) =>
    OFFLINE_MODE ? Promise.reject(new ApiError(503, "Offline mode is read-only; decisions require the backend.")) : request<{ run_id: string; status: string; decision: string; stream_url: string; timestamp: string }>(
      `/api/pipeline/${runId}/decision`,
      { method: "POST", body: JSON.stringify({ decision, note }) }
    ),

  cancelRun: (runId: string) => OFFLINE_MODE ? Promise.reject(new ApiError(503, "Offline mode is read-only; cancellation requires the backend.")) : request<{ run_id: string; status: string; timestamp: string }>(`/api/pipeline/${runId}/cancel`, { method: "POST" }),

  streamUrl: (runId: string, afterSeq?: number) =>
    `${API_BASE_URL}/api/pipeline/${runId}/stream${afterSeq !== undefined ? `?after_seq=${afterSeq}` : ""}`,

  // --- Graphs (Phase 5) --------------------------------------------------
  listGraphs: () => OFFLINE_MODE
    ? Promise.resolve({ graphs: Object.entries(OFFLINE_GRAPHS).map(([disease_slug, graph]) => ({ disease_slug, disease: String(graph.metadata.disease ?? disease_slug), node_count: graph.elements.nodes.length, edge_count: graph.elements.edges.length, version: null, updated: null, run_id: String(graph.metadata.run_id ?? "offline") })) })
    : request<{ graphs: GraphSummary[] }>("/api/graphs"),

  getGraph: (diseaseSlug: string) => OFFLINE_MODE
    ? OFFLINE_GRAPHS[diseaseSlug] ? Promise.resolve(OFFLINE_GRAPHS[diseaseSlug]) : Promise.reject(new ApiError(404, `Offline graph not found: ${diseaseSlug}`))
    : request<GraphResponse>(`/api/graphs/${diseaseSlug}`),

  // --- Eval flywheel (Phase 4) --------------------------------------------
  runEvalBackfill: () => OFFLINE_MODE ? Promise.resolve({ scored: 5, records: [] as EvalScore[] }) : request<{ scored: number; records: EvalScore[] }>("/api/eval/backfill", { method: "POST" }),

  getEvalDashboard: (subjectType?: string) =>
    OFFLINE_MODE ? Promise.resolve({ total_scored: 5, sessions_covered: ["asthma_001", "asthma_002", "asthma_003"], outcome_counts: { confirmed_false_positive_historical: 2, correctly_rejected: 1, accepted_pending_validation: 2 }, historical_gate_retroactive_catch_rate: 1, live_judge_agreement_rate: null }) : request<EvalDashboardMetrics>(`/api/eval/dashboard${qs({ subject_type: subjectType })}`),

  getEvalScores: (params?: { subject_type?: string; session_id?: string }) =>
    OFFLINE_MODE ? Promise.resolve({ scores: [] as EvalScore[] }) : request<{ scores: EvalScore[] }>(`/api/eval/scores${qs(params ?? {})}`),

  triggerJudge: (runId: string, payload: { hypothesis_id: string; statement: string; recombined_edges?: string[] }) =>
    OFFLINE_MODE ? Promise.reject(new ApiError(503, "Offline mode is read-only; live judging requires the backend.")) : request<{ run_id: string; hypothesis_id: string; verdict: JudgeVerdict }>(`/api/eval/judge/${runId}`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

export { API_BASE_URL };
