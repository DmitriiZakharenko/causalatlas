export type AutonomyLevel = "autocomplete" | "supervised" | "let_it_rip";
export type RunStatus = "pending" | "running" | "paused" | "completed" | "failed";
export type Decision = "approve" | "reject" | "edit";

export interface HumanIntervention {
  id: number;
  run_id: string;
  agent_name: string;
  decision: Decision;
  note: string | null;
  created_at: number;
}

export interface RunSummary {
  run_id: string;
  disease: string;
  gene: string | null;
  autonomy_level: AutonomyLevel;
  status: RunStatus;
  current_agent: string | null;
  error: string | null;
  session_id: string | null;
  created_at: number;
  updated_at: number;
}

export interface RunStatusResponse extends RunSummary {
  interventions: HumanIntervention[];
}

export interface StartRunResponse {
  run_id: string;
  status: "started";
  disease: string;
  gene: string | null;
  autonomy_level: AutonomyLevel;
  stream_url: string;
  timestamp: string;
}

/** One live-progress event as re-emitted over SSE by the orchestrator's
 * StreamTranslator (see backend/app/orchestrator.py) -- `type` doubles as
 * the SSE named-event name, so the frontend's EventSource listens for each
 * of these explicitly rather than relying on a generic `onmessage`. */
export type PipelineEvent =
  | { type: "skill_loaded"; skill: string; seq?: number }
  | { type: "agent_started"; agent: string; seq?: number }
  | { type: "agent_completed"; agent: string; seq?: number }
  | { type: "run_completed"; cost_usd?: number; duration_ms?: number; seq?: number }
  | { type: "run_failed"; reason: string; seq?: number }
  | { type: "run_paused"; agent: string | null; reason: string; seq?: number };

export const PIPELINE_EVENT_TYPES = [
  "skill_loaded",
  "agent_started",
  "agent_completed",
  "run_completed",
  "run_failed",
  "run_paused",
] as const;

export interface GraphSummary {
  disease_slug: string;
  disease: string;
  node_count: number;
  edge_count: number;
  version: string | null;
  updated: string | null;
}

export interface GraphNode {
  id: string;
  label: string;
  type: string | null;
  pmid_count: number;
  edge_count: number | null;
  sample_pmids: string[];
  looks_like_noise: boolean;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relation: string | null;
  relations: string[] | null;
  pmid_count: number;
  confidence: number | null;
  evidence_strength: string | null;
  sample_pmids: string[];
}

export interface GraphResponse {
  metadata: Record<string, unknown>;
  elements: { nodes: GraphNode[]; edges: GraphEdge[] };
}

export interface EvalScore {
  id: number;
  subject_type: "historical_backfill" | "live_judge";
  session_id: string;
  hypothesis_id: string | null;
  original_label: string | null;
  ground_truth: string | null;
  outcome: string;
  reasoning: string | null;
  created_at: number;
}

export interface EvalDashboardMetrics {
  total_scored: number;
  sessions_covered: string[];
  outcome_counts: Record<string, number>;
  historical_gate_retroactive_catch_rate: number | null;
  live_judge_agreement_rate: number | null;
}

export interface JudgeVerdict {
  hypothesis_id: string;
  independent_classification: "A" | "B" | "C" | "D" | "E";
  agrees_with_pipeline: boolean;
  reasoning: string;
  searches_run?: string[];
}
