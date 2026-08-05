export type AutonomyLevel = "autocomplete" | "supervised" | "let_it_rip";
export type RunStatus = "pending" | "running" | "paused" | "completed" | "failed" | "cancelled";
export type Decision = "approve" | "reject" | "edit";
export type AnalysisMode = "graph_only" | "full";

export interface AnalysisTarget {
  schema_version: "target.v1";
  disease: string | null;
  genes: string[];
  drugs: string[];
  tissues: string[];
  cell_types: string[];
  statistical_candidates?: Array<Record<string, unknown>>;
  query_mode: string | null;
}

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
  target_schema_version?: string | null;
  target?: AnalysisTarget | null;
  autonomy_level: AutonomyLevel;
  analysis_mode?: AnalysisMode;
  status: RunStatus;
  current_agent: string | null;
  error: string | null;
  session_id: string | null;
  created_at: number;
  updated_at: number;
  evidence_summary?: EvidenceSummary;
}

export interface RunStatusResponse extends RunSummary {
  interventions: HumanIntervention[];
}

export interface EvidenceSummary {
  run_id: string;
  execution: { status: RunStatus; complete: boolean; current_agent: string | null; error: string | null };
  evidence: {
    quality: "usable" | "degraded";
    verified_papers: number;
    corpus_papers?: number;
    rejected_papers: number;
    verification_count_discrepancy?: boolean;
    independent_sources: number;
    papers_per_mechanism_chain: { strategy: string; query: string; papers: number }[];
    fallback_count: number;
    fallback_files: string[];
    contradictions: number;
  };
  hypotheses: { novelty_candidates: number; d_e_candidates: number; generated: number; accepted: number; ready: boolean };
  hypothesis_records?: { id: string | null; class: string | null; source_gap: string | null; specific_prediction: string | null; falsification: string | null }[];
  experiment_design?: { status: string | null; hypothesis_id: string | null; model_system: string | null; experiments: { id?: string; method?: string; predicted_outcome?: string; falsification_criterion?: string }[]; primary_readout: string | null; negative_controls: string[] };
  budgets?: Record<string, { max_queries: number; max_publications: number; deadline_s: number }>;
  checkpoints?: string[];
  novelty_audits?: { hypothesis_id: string | null; classification: string | null; eligible: boolean; statement: string | null; action: string | null }[];
  novelty_catalog?: { source: string; hypothesis_id: string; classification: string; eligible: boolean; statement: string | null }[];
  artifacts: string[];
  replay_steps?: { number: string; title: string; description: string; metrics: string[]; artifact: string }[];
  demo?: { recorded: boolean; source: string; live: boolean };
}

export interface StartRunResponse {
  run_id: string;
  status: "started";
  disease: string | null;
  scope?: string;
  gene: string | null;
  target: AnalysisTarget;
  target_schema_version: string;
  autonomy_level: AutonomyLevel;
  analysis_mode: AnalysisMode;
  stream_url: string;
  timestamp: string;
}

/** One live-progress event as re-emitted over SSE by the orchestrator's
 * StreamTranslator (see backend/app/orchestrator.py) -- `type` doubles as
 * the SSE named-event name, so the frontend's EventSource listens for each
 * of these explicitly rather than relying on a generic `onmessage`. */
export type PipelineEvent =
  | { type: "skill_loaded"; skill: string; seq?: number; created_at?: number }
  | { type: "agent_started"; agent: string; seq?: number; created_at?: number }
  | { type: "agent_completed"; agent: string; seq?: number; created_at?: number }
  | {
      type: "run_completed";
      cost_usd?: number | null;
      duration_ms?: number;
      input_tokens?: number;
      output_tokens?: number;
      cached_input_tokens?: number;
      reasoning_tokens?: number;
      total_tokens?: number;
      usage_source?: string;
      llm_calls?: number;
      seq?: number;
      created_at?: number;
    }
  | { type: "run_failed"; reason: string; seq?: number; created_at?: number }
  | { type: "run_cancelled"; reason: string; seq?: number; created_at?: number }
  | { type: "run_paused"; agent: string | null; reason: string; seq?: number; created_at?: number };

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
  run_id?: string | null;
}

export interface GraphNode {
  id: string;
  label: string;
  type: string | null;
  pmid_count: number;
  edge_count: number | null;
  sample_pmids: string[];
  looks_like_noise: boolean;
  provenance_type?: string | null;
  source?: string | null;
  source_id?: string | null;
  is_input_only?: boolean;
  is_canonical_source?: boolean;
  canonical_statement?: string;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relation: string | null;
  relations: string[] | null;
  relation_variants?: string[];
  pmid_count: number;
  confidence: number | null;
  evidence_strength: string | null;
  sample_pmids: string[];
  claim_id?: string | null;
  provenance_type?: string | null;
  evidence_state?: string | null;
  evidence_states?: string[];
  sessions?: string[];
  context?: Record<string, unknown>;
  source_refs?: Array<Record<string, unknown> | string>;
  contradiction_group?: string | null;
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
