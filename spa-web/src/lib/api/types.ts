export interface TimerStartResponse {
  work_log_id: number;
  task_id: number;
  start_time: string;
}

export interface TimerStopResponse {
  work_log_id: number;
  task_id: number;
  duration_minutes: number;
  start_time: string;
  end_time: string;
  summary?: string | null;
}

export type NodeTypePath = "goal" | "objective" | "key_result" | "task";

export interface NodeMutationResponse {
  id: number;
  node_type: "GOAL" | "OBJECTIVE" | "KEY_RESULT" | "TASK";
  title: string;
  description?: string | null;
  progress?: number | null;
  owner_id?: number | null;
  updated_at?: string | null;
}

export interface NodeDeleteResponse {
  id: number;
  node_type: "GOAL" | "OBJECTIVE" | "KEY_RESULT" | "TASK";
  deleted: boolean;
}

export interface WorkLogDeleteResponse {
  id: number;
  deleted: boolean;
}

export interface CycleSummary {
  id: number;
  title: string;
  start_date?: string | null;
  end_date?: string | null;
  is_active: boolean;
  owner_manager_id?: number | null;
}

export interface CycleDeleteResponse {
  id: number;
  deleted: boolean;
}

export interface WeeklyPlanMutationResponse {
  id: number;
  user_id: number;
  week_start_date: string;
  week_end_date: string;
  priority_1: string;
  priority_2?: string | null;
  priority_3?: string | null;
  is_active: boolean;
}

export interface RetrospectiveMutationResponse {
  id: number;
  user_id: number;
  cycle_id?: number | null;
  week_start_date: string;
  content: string;
  sentiment?: string | null;
  created_at?: string | null;
}

export interface UserMutationResponse {
  id: number;
  username: string;
  display_name?: string | null;
  role: "admin" | "manager" | "member";
  manager_id?: number | null;
  team_id?: number | null;
  is_active: boolean;
  must_change_password: boolean;
}

export interface TeamMutationResponse {
  id: number;
  name: string;
  description?: string | null;
  created_at?: string | null;
}

export interface TeamDeleteResponse {
  id: number;
  deleted: boolean;
}

export interface UserPasswordResetResponse {
  user_id: number;
  reset: boolean;
}

export interface AdminAiHealthResponse {
  status?: string;
  provider?: string;
  external_ai_allowed?: boolean;
  configured?: boolean;
  config_message?: string;
  live_probe_enabled?: boolean;
  probe_ok?: boolean | null;
  probe_message?: string | null;
  probe_payload?: Record<string, unknown>;
}

export interface AdminPdfHealthResponse {
  environment?: string;
  platform?: string;
  method?: string;
  supported_method?: boolean;
  pdfshift_available?: boolean;
  playwright_available?: boolean;
  pdfshift_api_key_configured?: boolean;
  chromium_executable_detected?: boolean;
  chromium_executable_path?: string;
  managed_cloud_runtime?: boolean;
}

export interface AuditSummaryBucket {
  value: string | number | null;
  count: number;
}

export interface AuditEventSummary {
  id: number;
  actor?: string | null;
  actor_user_id?: number | null;
  actor_role?: string | null;
  actor_team_id?: number | null;
  action?: string | null;
  entity?: string | null;
  result?: string | null;
  target_type?: string | null;
  target_id?: number | null;
  target_owner_id?: number | null;
  target_team_id?: number | null;
  correlation_id?: string | null;
  request_id?: string | null;
  created_at?: string | null;
}

export interface AuditSummaryResponse {
  window_days?: number;
  recent_limit?: number;
  total_events?: number;
  success_events?: number;
  failure_events?: number;
  latest_event_at?: string | null;
  by_actor_role?: AuditSummaryBucket[];
  by_actor_team_id?: AuditSummaryBucket[];
  by_target_type?: AuditSummaryBucket[];
  by_entity?: AuditSummaryBucket[];
  by_action?: AuditSummaryBucket[];
  recent_events?: AuditEventSummary[];
}

export interface AdminDbRestoreResponse {
  format?: string;
  exported_at?: string;
  restored_counts?: Record<string, number>;
  unknown_tables?: string[];
}

export interface AsyncJobView {
  id: string;
  kind: string;
  status: string;
  result?: Record<string, unknown> | null;
  error_text?: string | null;
}

export interface AlignmentMutationResponse {
  id: number;
  parent_id: number;
  child_id: number;
  alignment_type: string;
  created_at?: string | null;
  created_by?: string | null;
}

export interface AlignmentDeleteResponse {
  id: number;
  deleted: boolean;
}

export interface ObjectiveAlignmentLinkMutationResponse {
  id: number;
  objective_id: number;
  linked_entity_type: string;
  linked_entity_id: number;
  direction: string;
  created_at?: string | null;
  created_by?: string | null;
}

export interface ObjectiveAlignmentLinkDeleteResponse {
  id: number;
  deleted: boolean;
}

export interface LeadershipMetricsResponse {
  hygiene_pct?: number;
  avg_confidence?: number;
  at_risk_count?: number;
  total_krs?: number;
  at_risk?: Array<Record<string, unknown>>;
  member_progress?: Array<Record<string, unknown>>;
  member_deadlines?: Array<Record<string, unknown>>;
  heatmap_data?: Array<Record<string, unknown>>;
}

export interface AiAnalyzeNodeResponse {
  efficiency_score?: number;
  effectiveness_score?: number;
  overall_score?: number;
  deadline_warnings?: string[];
  gap_analysis?: string;
  quality_assessment?: string;
  proposed_tasks?: Array<string | Record<string, unknown>>;
  summary?: string;
  analyzed_at?: string;
}

export interface AiTeamCoachResponse {
  coaching?: Record<string, unknown>;
}

export interface AiStrategyPulseResponse {
  subject_username?: string;
  cycle_id?: number;
  burnout_snapshot?: Record<string, unknown>;
  strategy_gaps?: Array<Record<string, unknown>>;
  predictive_outlook?: Record<string, unknown>;
  burnout_risk?: string;
  gap_signals?: string[];
  portfolio_actions?: string[];
}

export type CheckInVariationType = "COMMON_CAUSE" | "SPECIAL_CAUSE";

export interface CheckInMutationResponse {
  id: number;
  key_result_id: number;
  value: number;
  confidence_score: number;
  comment?: string | null;
  variation_type?: CheckInVariationType | null;
  special_cause_note?: string | null;
  experiment_id?: number | null;
  created_at?: string | null;
}

export type ExperimentStatusType = "PLANNED" | "RUNNING" | "DECIDED";
export type ExpectedEffectDirectionType = "UP" | "DOWN";

export interface ExperimentMutationResponse {
  id: number;
  key_result_id: number;
  cycle_id: number;
  created_by: string;
  hypothesis: string;
  change_description: string;
  start_at?: string | null;
  end_at?: string | null;
  status: ExperimentStatusType;
  decision?: "ADOPT" | "ITERATE" | "REVERT" | "UNKNOWN" | null;
  decision_rationale?: string | null;
  expected_effect_direction?: ExpectedEffectDirectionType | null;
  expected_effect_size?: number | null;
  created_at?: string | null;
}

export type ExperimentDecisionType = "ADOPT" | "ITERATE" | "REVERT" | "UNKNOWN";
