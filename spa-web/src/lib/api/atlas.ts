import type { AtlasSnapshotResponse } from "@/lib/atlas";
import type { SpaRolloutConfig } from "@/lib/rollout";

import {
  fetchWithTimeout,
  isTransientCycleQueryFailure,
  isTransientNetworkError,
  jsonHeaders,
  normalizeBackendDateTime,
  responseDetail,
  waitMs,
} from "@/lib/api/http";
import type {
  AlignmentDeleteResponse,
  AlignmentMutationResponse,
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
  const response = await fetch("/api/backend/v1/read/atlas/snapshot", {
    method: "POST",
    cache: "no-store",
    headers: jsonHeaders(input.actor_username),
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(`Atlas snapshot failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as AtlasSnapshotResponse;
}

export async function startTaskTimer(input: {
  actor_username: string;
  task_id: number;
  user_id?: string;
}): Promise<TimerStartResponse> {
  const response = await fetch("/api/backend/v1/timer/start", {
    method: "POST",
    headers: jsonHeaders(input.actor_username),
    body: JSON.stringify({
      task_id: input.task_id,
      user_id: input.user_id || input.actor_username,
    }),
  });
  if (!response.ok) {
    throw new Error(`Timer start failed: ${await responseDetail(response)}`);
  }
  const payload = (await response.json()) as TimerStartResponse;
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
  const response = await fetch("/api/backend/v1/timer/stop", {
    method: "POST",
    headers: jsonHeaders(input.actor_username),
    body: JSON.stringify({
      task_id: input.task_id,
      summary: input.summary || "",
      user_id: input.user_id || input.actor_username,
    }),
  });
  if (!response.ok) {
    throw new Error(`Timer stop failed: ${await responseDetail(response)}`);
  }
  const payload = (await response.json()) as TimerStopResponse;
  return {
    ...payload,
    start_time: normalizeBackendDateTime(payload.start_time),
    end_time: normalizeBackendDateTime(payload.end_time),
  };
}

export async function readSpaRolloutConfig(): Promise<SpaRolloutConfig> {
  const response = await fetch("/api/rollout", {
    method: "GET",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Rollout config fetch failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as SpaRolloutConfig;
}

export async function updateNodeMutation(input: {
  actor_username: string;
  node_type: NodeTypePath;
  node_id: number;
  updates: Record<string, unknown>;
}): Promise<NodeMutationResponse> {
  const response = await fetch(`/api/backend/v1/nodes/${input.node_type}/${input.node_id}`, {
    method: "PATCH",
    headers: jsonHeaders(input.actor_username),
    body: JSON.stringify({
      actor_username: input.actor_username,
      updates: input.updates,
    }),
  });
  if (!response.ok) {
    throw new Error(`Node update failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as NodeMutationResponse;
}

export async function createNodeMutation(input: {
  actor_username: string;
  create_type: NodeTypePath;
  payload: Record<string, unknown>;
}): Promise<NodeMutationResponse> {
  const response = await fetch(`/api/backend/v1/nodes/${input.create_type}`, {
    method: "POST",
    headers: jsonHeaders(input.actor_username),
    body: JSON.stringify({
      ...input.payload,
      actor_username: input.actor_username,
    }),
  });
  if (!response.ok) {
    throw new Error(`Node create failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as NodeMutationResponse;
}

export async function deleteNodeMutation(input: {
  actor_username: string;
  node_type: NodeTypePath;
  node_id: number;
}): Promise<NodeDeleteResponse> {
  const response = await fetch(`/api/backend/v1/nodes/${input.node_type}/${input.node_id}`, {
    method: "DELETE",
    headers: jsonHeaders(input.actor_username, false),
  });
  if (!response.ok) {
    throw new Error(`Node delete failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as NodeDeleteResponse;
}

export async function deleteWorkLogMutation(input: {
  actor_username: string;
  work_log_id: number;
}): Promise<WorkLogDeleteResponse> {
  const response = await fetch(`/api/backend/v1/work-logs/${input.work_log_id}`, {
    method: "DELETE",
    headers: jsonHeaders(input.actor_username, false),
  });
  if (!response.ok) {
    throw new Error(`Work log delete failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as WorkLogDeleteResponse;
}

export async function readCyclesQuery(input: {
  actor_username: string;
  kind: "cycles.active" | "cycles.all";
}): Promise<CycleSummary[]> {
  const maxAttempts = 4;
  const perAttemptTimeoutMs = 8_000;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    let response: Response;
    try {
      response = await fetchWithTimeout(
        "/api/backend/v1/read/query",
        {
          method: "POST",
          cache: "no-store",
          headers: jsonHeaders(input.actor_username),
          body: JSON.stringify({
            kind: input.kind,
            params: {},
            actor_username: input.actor_username,
          }),
        },
        perAttemptTimeoutMs,
      );
    } catch (error) {
      const retryable = isTransientNetworkError(error);
      if (retryable && attempt < maxAttempts) {
        await waitMs(250 * 2 ** (attempt - 1));
        continue;
      }
      throw new Error(
        `Cycle query failed: ${String(error instanceof Error ? error.message : error)}`,
      );
    }

    if (response.ok) {
      const payload = (await response.json()) as { cycles?: CycleSummary[] };
      return Array.isArray(payload.cycles) ? payload.cycles : [];
    }

    const detail = await responseDetail(response);
    const retryable = isTransientCycleQueryFailure(response.status, detail);
    if (retryable && attempt < maxAttempts) {
      await waitMs(250 * 2 ** (attempt - 1));
      continue;
    }
    throw new Error(`Cycle query failed: ${detail}`);
  }
  throw new Error("Cycle query failed: retry attempts exhausted.");
}

export async function createCycleMutation(input: {
  actor_username: string;
  title: string;
  start_date: string;
  end_date: string;
  is_active: boolean;
  owner_manager_id?: number;
}): Promise<CycleSummary> {
  const response = await fetch("/api/backend/v1/cycles", {
    method: "POST",
    headers: jsonHeaders(input.actor_username),
    body: JSON.stringify({
      actor_username: input.actor_username,
      title: input.title,
      start_date: input.start_date,
      end_date: input.end_date,
      is_active: input.is_active,
      owner_manager_id: input.owner_manager_id,
    }),
  });
  if (!response.ok) {
    throw new Error(`Cycle create failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as CycleSummary;
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
  const response = await fetch(`/api/backend/v1/cycles/${input.cycle_id}`, {
    method: "PATCH",
    headers: jsonHeaders(input.actor_username),
    body: JSON.stringify({
      actor_username: input.actor_username,
      title: input.title,
      start_date: input.start_date,
      end_date: input.end_date,
      is_active: input.is_active,
      owner_manager_id: input.owner_manager_id,
    }),
  });
  if (!response.ok) {
    throw new Error(`Cycle update failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as CycleSummary;
}

export async function deleteCycleMutation(input: {
  actor_username: string;
  cycle_id: number;
}): Promise<CycleDeleteResponse> {
  const response = await fetch(`/api/backend/v1/cycles/${input.cycle_id}`, {
    method: "DELETE",
    headers: jsonHeaders(input.actor_username, false),
  });
  if (!response.ok) {
    throw new Error(`Cycle delete failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as CycleDeleteResponse;
}

export async function readBackendQuery(input: {
  actor_username: string;
  kind: string;
  params?: Record<string, unknown>;
}): Promise<Record<string, unknown>> {
  const response = await fetch("/api/backend/v1/read/query", {
    method: "POST",
    cache: "no-store",
    headers: jsonHeaders(input.actor_username),
    body: JSON.stringify({
      kind: input.kind,
      params: input.params || {},
      actor_username: input.actor_username,
    }),
  });
  if (!response.ok) {
    throw new Error(`Read query failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as Record<string, unknown>;
}

export async function readLeadershipMetrics(input: {
  actor_username: string;
  cycle_id: number;
  usernames?: string[];
}): Promise<LeadershipMetricsResponse> {
  const response = await fetch("/api/backend/v1/read/leadership/metrics", {
    method: "POST",
    cache: "no-store",
    headers: jsonHeaders(input.actor_username),
    body: JSON.stringify({
      actor_username: input.actor_username,
      cycle_id: input.cycle_id,
      usernames: input.usernames || undefined,
    }),
  });
  if (!response.ok) {
    throw new Error(`Leadership metrics read failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as LeadershipMetricsResponse;
}

export async function createAlignmentMutation(input: {
  actor_username: string;
  parent_id: number;
  child_id: number;
  alignment_type?: string;
}): Promise<AlignmentMutationResponse> {
  const response = await fetch("/api/backend/v1/alignments", {
    method: "POST",
    headers: jsonHeaders(input.actor_username),
    body: JSON.stringify({
      actor_username: input.actor_username,
      parent_id: input.parent_id,
      child_id: input.child_id,
      alignment_type: input.alignment_type || "SUPPORTS",
    }),
  });
  if (!response.ok) {
    throw new Error(`Alignment create failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as AlignmentMutationResponse;
}

export async function deleteAlignmentMutation(input: {
  actor_username: string;
  edge_id: number;
}): Promise<AlignmentDeleteResponse> {
  const response = await fetch(`/api/backend/v1/alignments/${input.edge_id}`, {
    method: "DELETE",
    headers: jsonHeaders(input.actor_username, false),
  });
  if (!response.ok) {
    throw new Error(`Alignment delete failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as AlignmentDeleteResponse;
}
