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
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

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
    request<{ status: string; service: string; phase: string; pipeline_agents: string[]; timestamp: string }>(
      "/api/health"
    ),

  // --- Pipeline runs (Phase 2/3) ---------------------------------------
  startRun: (payload: {
    disease: string;
    gene?: string;
    autonomy_level?: AutonomyLevel;
    dev_pubmed_retmax?: number;
  }) =>
    request<StartRunResponse>("/api/pipeline/run", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listRuns: () => request<{ runs: RunSummary[] }>("/api/pipeline/runs"),

  getRunStatus: (runId: string) => request<RunStatusResponse>(`/api/pipeline/${runId}/status`),

  submitDecision: (runId: string, decision: "approve" | "reject" | "edit", note?: string) =>
    request<{ run_id: string; status: string; decision: string; stream_url: string; timestamp: string }>(
      `/api/pipeline/${runId}/decision`,
      { method: "POST", body: JSON.stringify({ decision, note }) }
    ),

  streamUrl: (runId: string, afterSeq?: number) =>
    `${API_BASE_URL}/api/pipeline/${runId}/stream${afterSeq !== undefined ? `?after_seq=${afterSeq}` : ""}`,

  // --- Graphs (Phase 5) --------------------------------------------------
  listGraphs: () => request<{ graphs: GraphSummary[] }>("/api/graphs"),

  getGraph: (diseaseSlug: string) => request<GraphResponse>(`/api/graphs/${diseaseSlug}`),

  // --- Eval flywheel (Phase 4) --------------------------------------------
  runEvalBackfill: () => request<{ scored: number; records: EvalScore[] }>("/api/eval/backfill", { method: "POST" }),

  getEvalDashboard: (subjectType?: string) =>
    request<EvalDashboardMetrics>(`/api/eval/dashboard${qs({ subject_type: subjectType })}`),

  getEvalScores: (params?: { subject_type?: string; session_id?: string }) =>
    request<{ scores: EvalScore[] }>(`/api/eval/scores${qs(params ?? {})}`),

  triggerJudge: (runId: string, payload: { hypothesis_id: string; statement: string; recombined_edges?: string[] }) =>
    request<{ run_id: string; hypothesis_id: string; verdict: JudgeVerdict }>(`/api/eval/judge/${runId}`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

export { API_BASE_URL };
