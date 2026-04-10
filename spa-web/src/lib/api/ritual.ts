import { jsonHeaders, jsonHeadersWithIdempotency, responseDetail } from "@/lib/api/http";
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
  const response = await fetch("/api/backend/v1/ai/analyze-node", {
    method: "POST",
    headers: jsonHeaders(input.actor_username),
    body: JSON.stringify({
      actor_username: input.actor_username,
      node_id: input.node_id,
      node_type: input.node_type,
    }),
  });
  if (!response.ok) {
    throw new Error(`AI node analysis failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as AiAnalyzeNodeResponse;
}

export async function analyzeTeamCoachAi(input: {
  actor_username: string;
  team_data: Record<string, unknown>;
}): Promise<AiTeamCoachResponse> {
  const response = await fetch("/api/backend/v1/ai/team-coach", {
    method: "POST",
    headers: jsonHeaders(input.actor_username),
    body: JSON.stringify({
      actor_username: input.actor_username,
      team_data: input.team_data,
    }),
  });
  if (!response.ok) {
    throw new Error(`AI team coach failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as AiTeamCoachResponse;
}

export async function readStrategyPulseAi(input: {
  actor_username: string;
  cycle_id: number;
  subject_username?: string;
  cycle_title?: string;
  days?: number;
}): Promise<AiStrategyPulseResponse> {
  const response = await fetch("/api/backend/v1/ai/strategy-pulse", {
    method: "POST",
    headers: jsonHeaders(input.actor_username),
    body: JSON.stringify({
      actor_username: input.actor_username,
      cycle_id: input.cycle_id,
      subject_username: input.subject_username || input.actor_username,
      cycle_title: input.cycle_title,
      days: input.days,
    }),
  });
  if (!response.ok) {
    throw new Error(`AI strategy pulse failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as AiStrategyPulseResponse;
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
  const response = await fetch("/api/backend/v1/weekly-plans", {
    method: "POST",
    headers: jsonHeaders(input.actor_username),
    body: JSON.stringify({
      actor_username: input.actor_username,
      user_id: input.user_id,
      start_date: input.start_date,
      end_date: input.end_date,
      p1: input.p1,
      p2: input.p2 || null,
      p3: input.p3 || null,
    }),
  });
  if (!response.ok) {
    throw new Error(`Weekly plan create failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as WeeklyPlanMutationResponse;
}

export async function createRetrospectiveMutation(input: {
  actor_username: string;
  user_id: number;
  cycle_id?: number;
  week_start_date: string;
  content: string;
  sentiment?: string;
}): Promise<RetrospectiveMutationResponse> {
  const response = await fetch("/api/backend/v1/retrospectives", {
    method: "POST",
    headers: jsonHeaders(input.actor_username),
    body: JSON.stringify({
      actor_username: input.actor_username,
      user_id: input.user_id,
      cycle_id: input.cycle_id,
      week_start_date: input.week_start_date,
      content: input.content,
      sentiment: input.sentiment || null,
    }),
  });
  if (!response.ok) {
    throw new Error(`Retrospective create failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as RetrospectiveMutationResponse;
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
  const response = await fetch("/api/backend/v1/check-ins", {
    method: "POST",
    headers: jsonHeaders(input.actor_username),
    body: JSON.stringify({
      actor_username: input.actor_username,
      kr_id: input.kr_id,
      value: input.value,
      confidence: input.confidence,
      comment: input.comment || "",
      variation_type: input.variation_type || "COMMON_CAUSE",
      special_cause_note: input.special_cause_note || null,
      experiment_id: input.experiment_id,
    }),
  });
  if (!response.ok) {
    throw new Error(`Check-in create failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as CheckInMutationResponse;
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
  const response = await fetch("/api/backend/v1/experiments", {
    method: "POST",
    headers: jsonHeadersWithIdempotency(
      input.actor_username,
      "experiments.create",
      requestPayload,
    ),
    body: JSON.stringify(requestPayload),
  });
  if (!response.ok) {
    throw new Error(`Experiment create failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as ExperimentMutationResponse;
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
  const response = await fetch(`/api/backend/v1/experiments/${input.experiment_id}`, {
    method: "PATCH",
    headers: jsonHeadersWithIdempotency(
      input.actor_username,
      `experiments.update.${input.experiment_id}`,
      requestPayload,
    ),
    body: JSON.stringify(requestPayload),
  });
  if (!response.ok) {
    throw new Error(`Experiment update failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as ExperimentMutationResponse;
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
  const response = await fetch(`/api/backend/v1/experiments/${input.experiment_id}/close`, {
    method: "POST",
    headers: jsonHeadersWithIdempotency(
      input.actor_username,
      `experiments.close.${input.experiment_id}`,
      requestPayload,
    ),
    body: JSON.stringify(requestPayload),
  });
  if (!response.ok) {
    throw new Error(`Experiment close failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as ExperimentMutationResponse;
}
