import type { BackendSchemas } from "@/lib/api/backend-schema";

export type TimerStartResponse = BackendSchemas["TimerStartResponse"];
export type TimerStopResponse = BackendSchemas["TimerStopResponse"];

export type NodeTypePath = "goal" | "objective" | "key_result" | "task";

export type NodeMutationResponse = BackendSchemas["NodeMutationView"];
export type NodeDeleteResponse = BackendSchemas["NodeDeleteResponse"];
export type WorkLogDeleteResponse = BackendSchemas["WorkLogDeleteResponse"];
/** UI view intentionally permits incomplete historical-cycle dates. */
export interface CycleSummary {
  id: number;
  title: string;
  start_date?: string | null;
  end_date?: string | null;
  is_active: boolean;
  owner_manager_id?: number | null;
}
export type CycleDeleteResponse = BackendSchemas["CycleDeleteResponse"];
export type WeeklyPlanMutationResponse = BackendSchemas["WeeklyPlanMutationView"];
export type RetrospectiveMutationResponse = BackendSchemas["RetrospectiveMutationView"];
export type UserMutationResponse = BackendSchemas["UserMutationView"];
export type TeamMutationResponse = BackendSchemas["TeamMutationView"];
export type TeamDeleteResponse = BackendSchemas["TeamDeleteResponse"];
export type UserPasswordResetResponse = BackendSchemas["UserPasswordResetResponse"];

export type AdminAiHealthResponse = BackendSchemas["AdminAiHealthResponse"];
export type AdminPdfHealthResponse = BackendSchemas["AdminPdfHealthResponse"];

/** Screen-facing projection of the generic generated read-query result. */
export interface AuditSummaryBucketView {
  value: string | number | null;
  count: number;
}

export interface AuditEventSummaryView {
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

export interface AuditSummaryView {
  window_days?: number;
  recent_limit?: number;
  total_events?: number;
  success_events?: number;
  failure_events?: number;
  latest_event_at?: string | null;
  by_actor_role?: AuditSummaryBucketView[];
  by_actor_team_id?: AuditSummaryBucketView[];
  by_target_type?: AuditSummaryBucketView[];
  by_entity?: AuditSummaryBucketView[];
  by_action?: AuditSummaryBucketView[];
  recent_events?: AuditEventSummaryView[];
}

export type AdminDbRestoreResponse = BackendSchemas["AdminDbRestoreResponse"];

// AsyncJobView moved to generated types: see lib/api/jobs.ts
// (type alias to components["schemas"]["JobView"] from the OpenAPI artifact).

export type AlignmentMutationResponse = BackendSchemas["AlignmentMutationView"];
export type AlignmentDeleteResponse = BackendSchemas["AlignmentDeleteResponse"];
export type ObjectiveAlignmentLinkMutationResponse = BackendSchemas["ObjectiveAlignmentLinkMutationView"];
export type ObjectiveAlignmentLinkDeleteResponse = BackendSchemas["ObjectiveAlignmentLinkDeleteResponse"];

export type LeadershipMetricsResponse = BackendSchemas["LeadershipMetricsResponse"];
export type AiAnalyzeNodeResponse = BackendSchemas["AiAnalyzeNodeResponse"];
export type AiTeamCoachResponse = BackendSchemas["AiTeamCoachResponse"];
export type AiStrategyPulseResponse = BackendSchemas["AiStrategyPulseResponse"];

export type CheckInVariationType = "COMMON_CAUSE" | "SPECIAL_CAUSE";

export type CheckInMutationResponse = BackendSchemas["CheckInMutationView"];

export type ExperimentStatusType = "PLANNED" | "RUNNING" | "DECIDED";
export type ExpectedEffectDirectionType = "UP" | "DOWN";

export type ExperimentMutationResponse = BackendSchemas["ExperimentMutationView"];

export type ExperimentDecisionType = "ADOPT" | "ITERATE" | "REVERT" | "UNKNOWN";
