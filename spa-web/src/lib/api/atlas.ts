import type { AtlasSnapshotResponse } from "@/lib/atlas";
import type {
  AtlasSnapshotRequest,
  ReadQueryRequest,
  ReadQueryResponse,
} from "@/lib/api/backend-schema";

import { backendJsonRequest, normalizeBackendDateTime, retryBackendJsonRequest } from "@/lib/api/http";
import type {
  AlignmentDeleteResponse,
  AlignmentMutationResponse,
  ObjectiveAlignmentLinkDeleteResponse,
  ObjectiveAlignmentLinkMutationResponse,
  CycleDeleteResponse,
  CycleSummary,
  LeadershipMetricsResponse,
  NodeDeleteResponse,
  NodeMutationResponse,
  NodeTypePath,
  TimerStartResponse,
  TimerStopResponse,
  WorkLogDeleteResponse,
} from "@/lib/api/types";

export async function readAtlasSnapshot(input: {
  actor_username: string;
  cycle_id: number;
  owner_ids?: number[];
  include_analysis?: boolean;
}): Promise<AtlasSnapshotResponse> {
  const requestBody: AtlasSnapshotRequest = {
    actor_username: input.actor_username,
    cycle_id: input.cycle_id,
    ...(input.owner_ids ? { owner_ids: input.owner_ids } : {}),
    include_analysis: Boolean(input.include_analysis),
  };
  const snapshot = await backendJsonRequest({
    operation: "api_read_atlas_snapshot_v1_read_atlas_snapshot_post",
    path: "/v1/read/atlas/snapshot",
    actor: input.actor_username,
    label: "Atlas snapshot",
    cache: "no-store",
    body: requestBody,
  });
  return {
    goals: (snapshot.goals || []).map((goal) => ({
      ...goal,
      title: goal.title || "",
      description: goal.description || "",
      progress: goal.progress || 0,
      owner_id: goal.owner_id || 0,
      objectives: (goal.objectives || []).map((objective) => ({
        ...objective,
        title: objective.title || "",
        description: objective.description || "",
        progress: objective.progress || 0,
        key_results: (objective.key_results || []).map((keyResult) => ({
          ...keyResult,
          title: keyResult.title || "",
          description: keyResult.description || "",
          progress: keyResult.progress || 0,
          tasks: (keyResult.tasks || []).map((task) => ({
            ...task,
            title: task.title || "",
            description: task.description || "",
            progress: task.progress || 0,
            status: task.status || "",
            total_time_spent: task.total_time_spent || 0,
            estimated_minutes: task.estimated_minutes || 0,
            deadline: task.deadline ?? null,
            timer_started_at: task.timer_started_at ?? null,
            assignee_id: task.assignee_id ?? null,
          })),
        })),
      })),
    })),
    users_map: Object.fromEntries(
      Object.entries(snapshot.users_map || {}).map(([id, name]) => [String(id), String(name || "")]),
    ),
  };
}

export async function startTaskTimer(input: {
  actor_username: string;
  task_id: number;
  user_id?: string;
}): Promise<TimerStartResponse> {
  const payload = await backendJsonRequest({
    operation: "api_start_timer_v1_timer_start_post",
    path: "/v1/timer/start",
    actor: input.actor_username,
    label: "Timer start",
    body: {
      task_id: input.task_id,
      user_id: input.user_id || input.actor_username,
    },
  });
  return {
    ...payload,
    start_time: normalizeBackendDateTime(payload.start_time),
  };
}

export async function stopTaskTimer(input: {
  actor_username: string;
  task_id: number;
  summary?: string;
  user_id?: string;
}): Promise<TimerStopResponse> {
  const payload = await backendJsonRequest({
    operation: "api_stop_timer_v1_timer_stop_post",
    path: "/v1/timer/stop",
    actor: input.actor_username,
    label: "Timer stop",
    body: {
      task_id: input.task_id,
      summary: input.summary || "",
      user_id: input.user_id || input.actor_username,
    },
  });
  return {
    ...payload,
    start_time: normalizeBackendDateTime(payload.start_time),
    end_time: normalizeBackendDateTime(payload.end_time),
  };
}

export async function updateNodeMutation(input: {
  actor_username: string;
  node_type: NodeTypePath;
  node_id: number;
  updates: Record<string, unknown>;
}): Promise<NodeMutationResponse> {
  return backendJsonRequest({
    operation: "api_update_node_v1_nodes__node_type___node_id__patch",
    path: `/v1/nodes/${input.node_type}/${input.node_id}`,
    actor: input.actor_username,
    label: "Node update",
    body: {
      actor_username: input.actor_username,
      updates: input.updates,
    },
  });
}

export async function createNodeMutation(input: {
  actor_username: string;
  create_type: NodeTypePath;
  payload: Record<string, unknown>;
}): Promise<NodeMutationResponse> {
  const title = requiredText(input.payload, "title");
  const description = requiredText(input.payload, "description");
  if (input.create_type === "goal") {
    return backendJsonRequest({
      operation: "api_create_goal_v1_nodes_goal_post",
      path: "/v1/nodes/goal",
      actor: input.actor_username,
      label: "Goal create",
      body: {
        actor_username: input.actor_username,
        user_id: requiredText(input.payload, "user_id"),
        title,
        description,
        cycle_id: optionalNumber(input.payload, "cycle_id"),
        strategy_tags: optionalStringList(input.payload, "strategy_tags"),
      },
    });
  }
  if (input.create_type === "objective") {
    return backendJsonRequest({
      operation: "api_create_objective_v1_nodes_objective_post",
      path: "/v1/nodes/objective",
      actor: input.actor_username,
      label: "Objective create",
      body: {
        actor_username: input.actor_username,
        goal_id: requiredPositiveInteger(input.payload, "goal_id"),
        title,
        description,
      },
    });
  }
  if (input.create_type === "key_result") {
    return backendJsonRequest({
      operation: "api_create_key_result_v1_nodes_key_result_post",
      path: "/v1/nodes/key_result",
      actor: input.actor_username,
      label: "Key result create",
      body: {
        actor_username: input.actor_username,
        objective_id: requiredPositiveInteger(input.payload, "objective_id"),
        title,
        description,
        target_value: requiredNumber(input.payload, "target_value"),
        unit: requiredText(input.payload, "unit"),
        initiative_tags: optionalStringList(input.payload, "initiative_tags"),
      },
    });
  }
  return backendJsonRequest({
    operation: "api_create_task_v1_nodes_task_post",
    path: "/v1/nodes/task",
    actor: input.actor_username,
    label: "Task create",
    body: {
      actor_username: input.actor_username,
      key_result_id: requiredPositiveInteger(input.payload, "key_result_id"),
      title,
      description,
      estimated_minutes: requiredNumber(input.payload, "estimated_minutes"),
      deadline: optionalText(input.payload, "deadline"),
    },
  });
}

function requiredText(payload: Record<string, unknown>, field: string): string {
  const value = typeof payload[field] === "string" ? payload[field].trim() : "";
  if (!value) {
    throw new Error(`Node create requires ${field}.`);
  }
  return value;
}

function optionalText(payload: Record<string, unknown>, field: string): string | undefined {
  const value = payload[field];
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function requiredNumber(payload: Record<string, unknown>, field: string): number {
  const value = payload[field];
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new Error(`Node create requires numeric ${field}.`);
  }
  return value;
}

function requiredPositiveInteger(payload: Record<string, unknown>, field: string): number {
  const value = requiredNumber(payload, field);
  if (!Number.isInteger(value) || value <= 0) {
    throw new Error(`Node create requires positive integer ${field}.`);
  }
  return value;
}

function optionalNumber(payload: Record<string, unknown>, field: string): number | undefined {
  const value = payload[field];
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function optionalStringList(
  payload: Record<string, unknown>,
  field: string,
): string[] | undefined {
  const value = payload[field];
  return Array.isArray(value) && value.every((item) => typeof item === "string")
    ? value
    : undefined;
}

export async function deleteNodeMutation(input: {
  actor_username: string;
  node_type: NodeTypePath;
  node_id: number;
}): Promise<NodeDeleteResponse> {
  return backendJsonRequest({
    operation: "api_delete_node_v1_nodes__node_type___node_id__delete",
    path: `/v1/nodes/${input.node_type}/${input.node_id}`,
    actor: input.actor_username,
    label: "Node delete",
  });
}

export async function deleteWorkLogMutation(input: {
  actor_username: string;
  work_log_id: number;
}): Promise<WorkLogDeleteResponse> {
  return backendJsonRequest({
    operation: "api_delete_work_log_v1_work_logs__work_log_id__delete",
    path: `/v1/work-logs/${input.work_log_id}`,
    actor: input.actor_username,
    label: "Work log delete",
  });
}

export async function readCyclesQuery(input: {
  actor_username: string;
  kind: "cycles.active" | "cycles.all";
}): Promise<CycleSummary[]> {
  const payload = await retryBackendJsonRequest({
    operation: "api_read_query_v1_read_query_post",
    path: "/v1/read/query",
    actor: input.actor_username,
    body: { kind: input.kind, params: {}, actor_username: input.actor_username },
    // Supabase free-tier wake-up and pooler latency can exceed 8 seconds for
    // Check-In's multi-query workspace load, so the budget stays explicit at
    // 120s rather than falling back to the helper's 8s default.
    label: "Cycle query",
    perAttemptTimeoutMs: 120_000,
  });
  return Array.isArray(payload.cycles) ? payload.cycles : [];
}

export async function createCycleMutation(input: {
  actor_username: string;
  title: string;
  start_date: string;
  end_date: string;
  is_active: boolean;
  owner_manager_id?: number;
}): Promise<CycleSummary> {
  return backendJsonRequest({
    operation: "api_create_cycle_v1_cycles_post",
    path: "/v1/cycles",
    actor: input.actor_username,
    label: "Cycle create",
    body: {
      actor_username: input.actor_username,
      title: input.title,
      start_date: input.start_date,
      end_date: input.end_date,
      is_active: input.is_active,
      owner_manager_id: input.owner_manager_id,
    },
  });
}

export async function updateCycleMutation(input: {
  actor_username: string;
  cycle_id: number;
  title: string;
  start_date: string;
  end_date: string;
  is_active: boolean;
  owner_manager_id?: number;
}): Promise<CycleSummary> {
  return backendJsonRequest({
    operation: "api_update_cycle_v1_cycles__cycle_id__patch",
    path: `/v1/cycles/${input.cycle_id}`,
    actor: input.actor_username,
    label: "Cycle update",
    body: {
      actor_username: input.actor_username,
      title: input.title,
      start_date: input.start_date,
      end_date: input.end_date,
      is_active: input.is_active,
      owner_manager_id: input.owner_manager_id,
    },
  });
}

export async function deleteCycleMutation(input: {
  actor_username: string;
  cycle_id: number;
}): Promise<CycleDeleteResponse> {
  return backendJsonRequest({
    operation: "api_delete_cycle_v1_cycles__cycle_id__delete",
    path: `/v1/cycles/${input.cycle_id}`,
    actor: input.actor_username,
    label: "Cycle delete",
  });
}

export async function readBackendQuery(input: {
  actor_username: string;
  kind: string;
  params?: Record<string, unknown>;
}): Promise<ReadQueryResponse> {
  const requestBody: ReadQueryRequest = {
    actor_username: input.actor_username,
    kind: input.kind,
    params: input.params || {},
  };
  return retryBackendJsonRequest({
    operation: "api_read_query_v1_read_query_post",
    path: "/v1/read/query",
    actor: input.actor_username,
    body: requestBody,
    // Keep the browser timeout aligned with the BFF's read-query budget.
    label: "Read query",
    perAttemptTimeoutMs: 120_000,
  });
}

export async function readLeadershipMetrics(input: {
  actor_username: string;
  cycle_id: number;
  usernames?: string[];
}): Promise<LeadershipMetricsResponse> {
  return backendJsonRequest({
    operation: "api_read_leadership_metrics_v1_read_leadership_metrics_post",
    path: "/v1/read/leadership/metrics",
    actor: input.actor_username,
    label: "Leadership metrics read",
    cache: "no-store",
    body: {
      actor_username: input.actor_username,
      cycle_id: input.cycle_id,
      usernames: input.usernames || undefined,
    },
  });
}

export async function createAlignmentMutation(input: {
  actor_username: string;
  parent_id: number;
  child_id: number;
  alignment_type?: string;
}): Promise<AlignmentMutationResponse> {
  return backendJsonRequest({
    operation: "api_create_alignment_v1_alignments_post",
    path: "/v1/alignments",
    actor: input.actor_username,
    label: "Alignment create",
    body: {
      actor_username: input.actor_username,
      parent_id: input.parent_id,
      child_id: input.child_id,
      alignment_type: input.alignment_type || "SUPPORTS",
    },
  });
}

export async function deleteAlignmentMutation(input: {
  actor_username: string;
  edge_id: number;
}): Promise<AlignmentDeleteResponse> {
  return backendJsonRequest({
    operation: "api_delete_alignment_v1_alignments__edge_id__delete",
    path: `/v1/alignments/${input.edge_id}`,
    actor: input.actor_username,
    label: "Alignment delete",
  });
}

export async function createObjectiveAlignmentLinkMutation(input: {
  actor_username: string;
  objective_id: number;
  linked_entity_type: "goal" | "key_result";
  linked_entity_id: number;
  direction: "parent" | "child";
}): Promise<ObjectiveAlignmentLinkMutationResponse> {
  return backendJsonRequest({
    operation: "api_create_objective_alignment_link_v1_objective_alignment_links_post",
    path: "/v1/objective-alignment-links",
    actor: input.actor_username,
    label: "Alignment link create",
    body: {
      actor_username: input.actor_username,
      objective_id: input.objective_id,
      linked_entity_type: input.linked_entity_type,
      linked_entity_id: input.linked_entity_id,
      direction: input.direction,
    },
  });
}

export async function deleteObjectiveAlignmentLinkMutation(input: {
  actor_username: string;
  link_id: number;
}): Promise<ObjectiveAlignmentLinkDeleteResponse> {
  return backendJsonRequest({
    operation: "api_delete_objective_alignment_link_v1_objective_alignment_links__link_id__delete",
    path: `/v1/objective-alignment-links/${input.link_id}`,
    actor: input.actor_username,
    label: "Alignment link delete",
  });
}
