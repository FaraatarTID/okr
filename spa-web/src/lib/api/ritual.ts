import { backendJsonRequest, jsonHeadersWithIdempotency } from "@/lib/api/http";
import type {
  AiAnalyzeNodeResponse,
  AiStrategyPulseResponse,
  AiTeamCoachResponse,
  CheckInMutationResponse,
  CheckInVariationType,
  ExperimentDecisionType,
  ExperimentMutationResponse,
  ExpectedEffectDirectionType,
  RetrospectiveMutationResponse,
  WeeklyPlanMutationResponse,
} from "@/lib/api/types";

export async function analyzeNodeAi(input: {
  actor_username: string;
  node_id: number;
  node_type: "GOAL" | "OBJECTIVE" | "KEY_RESULT" | "TASK";
}): Promise<AiAnalyzeNodeResponse> {
  return backendJsonRequest({
    operation: "api_ai_analyze_node_v1_ai_analyze_node_post",
    path: "/v1/ai/analyze-node",
    actor: input.actor_username,
    label: "AI node analysis",
    body: {
      actor_username: input.actor_username,
      node_id: input.node_id,
      node_type: input.node_type,
    },
  });
}

export async function analyzeTeamCoachAi(input: {
  actor_username: string;
  team_data: Record<string, unknown>;
}): Promise<AiTeamCoachResponse> {
  return backendJsonRequest({
    operation: "api_ai_team_coach_v1_ai_team_coach_post",
    path: "/v1/ai/team-coach",
    actor: input.actor_username,
    label: "AI team coach",
    body: {
      actor_username: input.actor_username,
      team_data: input.team_data,
    },
  });
}

export async function readStrategyPulseAi(input: {
  actor_username: string;
  cycle_id: number;
  subject_username?: string;
  cycle_title?: string;
  days?: number;
}): Promise<AiStrategyPulseResponse> {
  return backendJsonRequest({
    operation: "api_ai_strategy_pulse_v1_ai_strategy_pulse_post",
    path: "/v1/ai/strategy-pulse",
    actor: input.actor_username,
    label: "AI strategy pulse",
    body: {
      actor_username: input.actor_username,
      cycle_id: input.cycle_id,
      subject_username: input.subject_username || input.actor_username,
      cycle_title: input.cycle_title,
      days: input.days ?? 14,
    },
  });
}

export async function createWeeklyPlanMutation(input: {
  actor_username: string;
  user_id: number;
  start_date: string;
  end_date: string;
  p1: string;
  p2?: string;
  p3?: string;
}): Promise<WeeklyPlanMutationResponse> {
  return backendJsonRequest({
    operation: "api_create_weekly_plan_v1_weekly_plans_post",
    path: "/v1/weekly-plans",
    actor: input.actor_username,
    label: "Weekly plan create",
    body: {
      actor_username: input.actor_username,
      user_id: input.user_id,
      start_date: input.start_date,
      end_date: input.end_date,
      p1: input.p1,
      p2: input.p2 || null,
      p3: input.p3 || null,
    },
  });
}

export async function createRetrospectiveMutation(input: {
  actor_username: string;
  user_id: number;
  cycle_id?: number;
  week_start_date: string;
  content: string;
  sentiment?: string;
}): Promise<RetrospectiveMutationResponse> {
  return backendJsonRequest({
    operation: "api_create_retrospective_v1_retrospectives_post",
    path: "/v1/retrospectives",
    actor: input.actor_username,
    label: "Retrospective create",
    body: {
      actor_username: input.actor_username,
      user_id: input.user_id,
      cycle_id: input.cycle_id,
      week_start_date: input.week_start_date,
      content: input.content,
      sentiment: input.sentiment || null,
    },
  });
}

export async function createCheckInMutation(input: {
  actor_username: string;
  kr_id: number;
  value: number;
  confidence: number;
  comment?: string;
  variation_type?: CheckInVariationType;
  special_cause_note?: string;
  experiment_id?: number;
}): Promise<CheckInMutationResponse> {
  return backendJsonRequest({
    operation: "api_create_check_in_v1_check_ins_post",
    path: "/v1/check-ins",
    actor: input.actor_username,
    label: "Check-in create",
    body: {
      actor_username: input.actor_username,
      kr_id: input.kr_id,
      value: input.value,
      confidence: input.confidence,
      comment: input.comment || "",
      variation_type: input.variation_type || "COMMON_CAUSE",
      special_cause_note: input.special_cause_note || null,
      experiment_id: input.experiment_id,
    },
  });
}

export async function createExperimentMutation(input: {
  actor_username: string;
  key_result_id: number;
  cycle_id: number;
  hypothesis: string;
  change_description: string;
  start_at?: string;
  expected_effect_direction?: ExpectedEffectDirectionType;
  expected_effect_size?: number;
}): Promise<ExperimentMutationResponse> {
  const requestPayload = {
    actor_username: input.actor_username,
    key_result_id: input.key_result_id,
    cycle_id: input.cycle_id,
    hypothesis: input.hypothesis,
    change_description: input.change_description,
    start_at: input.start_at || null,
    expected_effect_direction: input.expected_effect_direction || null,
    expected_effect_size: input.expected_effect_size,
  };
  return backendJsonRequest({
    operation: "api_create_experiment_v1_experiments_post",
    path: "/v1/experiments",
    actor: input.actor_username,
    label: "Experiment create",
    headers: jsonHeadersWithIdempotency(
      input.actor_username,
      "experiments.create",
      requestPayload,
    ),
    body: requestPayload,
  });
}

export async function updateExperimentMutation(input: {
  actor_username: string;
  experiment_id: number;
  updates: Record<string, unknown>;
}): Promise<ExperimentMutationResponse> {
  const requestPayload = {
    actor_username: input.actor_username,
    updates: input.updates,
  };
  return backendJsonRequest({
    operation: "api_update_experiment_v1_experiments__experiment_id__patch",
    path: `/v1/experiments/${input.experiment_id}`,
    actor: input.actor_username,
    label: "Experiment update",
    headers: jsonHeadersWithIdempotency(
      input.actor_username,
      `experiments.update.${input.experiment_id}`,
      requestPayload,
    ),
    body: requestPayload,
  });
}

export async function closeExperimentMutation(input: {
  actor_username: string;
  experiment_id: number;
  decision: ExperimentDecisionType;
  rationale?: string;
}): Promise<ExperimentMutationResponse> {
  const requestPayload = {
    actor_username: input.actor_username,
    decision: input.decision,
    rationale: input.rationale || "",
  };
  return backendJsonRequest({
    operation: "api_close_experiment_v1_experiments__experiment_id__close_post",
    path: `/v1/experiments/${input.experiment_id}/close`,
    actor: input.actor_username,
    label: "Experiment close",
    headers: jsonHeadersWithIdempotency(
      input.actor_username,
      `experiments.close.${input.experiment_id}`,
      requestPayload,
    ),
    body: requestPayload,
  });
}
