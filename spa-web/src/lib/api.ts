import type { AtlasSnapshotResponse } from "@/lib/atlas";
import type { SpaRolloutConfig } from "@/lib/rollout";

export interface AuthUser {
  id: number;
  username: string;
  display_name: string;
  role: string;
  team_id?: number | null;
  manager_id?: number | null;
  must_change_password?: boolean;
}

export interface AuthResponse {
  user?: AuthUser;
  success?: boolean;
  error_code?: string;
  detail?: string;
}

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
  decision?: "ADOPT" | "ITERATE" | "ABANDON" | null;
  decision_rationale?: string | null;
  expected_effect_direction?: ExpectedEffectDirectionType | null;
  expected_effect_size?: number | null;
  created_at?: string | null;
}

export type ExperimentDecisionType = "ADOPT" | "ITERATE" | "ABANDON";

async function responseDetail(response: Response): Promise<string> {
  let detail = `${response.status}`;
  try {
    const payload = (await response.json()) as {
      detail?: string;
      error?: string;
      error_code?: string;
      bff_origin?: string;
    };
    const message = String(payload.error || payload.detail || payload.error_code || detail);
    const reason = String(payload.detail || "").trim();
    const bffOrigin = String(payload.bff_origin || "").trim();
    const extra: string[] = [];
    if (reason && reason !== message) {
      extra.push(`reason: ${reason}`);
    }
    if (bffOrigin) {
      extra.push(`bff_origin: ${bffOrigin}`);
    }
    detail = extra.length > 0 ? `${message} (${extra.join("; ")})` : message;
  } catch {
    // ignore body parse failure
  }
  return detail;
}

function waitMs(durationMs: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, Math.max(0, Math.floor(durationMs)));
  });
}

async function fetchWithTimeout(
  url: string,
  init: RequestInit,
  timeoutMs: number,
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), Math.max(1, Math.floor(timeoutMs)));
  try {
    return await fetch(url, {
      ...init,
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timer);
  }
}

function isTransientNetworkError(error: unknown): boolean {
  const text = String(error instanceof Error ? error.message : error || "")
    .trim()
    .toLowerCase();
  if (!text) {
    return false;
  }
  return (
    text.includes("socket hang up") ||
    text.includes("econnreset") ||
    text.includes("econnrefused") ||
    text.includes("etimedout") ||
    text.includes("aborted") ||
    text.includes("networkerror") ||
    text.includes("fetch failed")
  );
}

function isTransientCycleQueryFailure(status: number, detail: string): boolean {
  if (status >= 500) {
    return true;
  }
  const normalized = String(detail || "").trim().toLowerCase();
  return (
    normalized.includes("socket hang up") ||
    normalized.includes("econnreset") ||
    normalized.includes("econnrefused") ||
    normalized.includes("etimedout") ||
    normalized.includes("timeout")
  );
}

function normalizeBackendDateTime(value: unknown): string {
  const text = String(value || "").trim();
  if (!text) {
    return "";
  }
  const matched = text.match(
    /^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})(?:\.(\d+))?([zZ]|[+\-]\d{2}:\d{2})?$/,
  );
  if (!matched) {
    return text;
  }
  const [, datePart, timePart, fractionalRaw, timezoneRaw] = matched;
  const fractional = fractionalRaw ? `.${fractionalRaw.slice(0, 3).padEnd(3, "0")}` : "";
  const timezone = timezoneRaw ? (timezoneRaw.toUpperCase() === "Z" ? "Z" : timezoneRaw) : "Z";
  return `${datePart}T${timePart}${fractional}${timezone}`;
}

function stableStringHash(text: string): string {
  let hash = 0x811c9dc5;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = (hash * 0x01000193) >>> 0;
  }
  return hash.toString(16).padStart(8, "0");
}

function idempotencyKey(scope: string, payload: unknown): string {
  const serialized = JSON.stringify(payload ?? {});
  const bucket = Math.floor(Date.now() / 15_000);
  return `${scope}:${bucket}:${stableStringHash(serialized)}`.slice(0, 255);
}

function jsonHeadersWithIdempotency(
  actor: string | undefined,
  scope: string,
  payload: unknown,
): Record<string, string> {
  return {
    ...jsonHeaders(actor),
    "x-okr-idempotency-key": idempotencyKey(scope, payload),
  };
}

function jsonHeaders(actor?: string): Record<string, string> {
  const headers: Record<string, string> = {
    "content-type": "application/json",
  };
  if (actor) {
    headers["x-okr-actor"] = actor;
  }
  return headers;
}

export async function bffLogin(input: {
  username: string;
  password: string;
  client_ip?: string;
}): Promise<AuthResponse> {
  const response = await fetch("/api/backend/v1/auth/login", {
    method: "POST",
    headers: jsonHeaders(),
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(`Login failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as AuthResponse;
}

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
    headers: jsonHeaders(input.actor_username),
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
    headers: jsonHeaders(input.actor_username),
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
    headers: jsonHeaders(input.actor_username),
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

export async function createUserMutation(input: {
  actor_username: string;
  username: string;
  password: string;
  role: "admin" | "manager" | "member";
  display_name?: string;
  manager_id?: number;
  team_id?: number;
  must_change_password?: boolean;
}): Promise<UserMutationResponse> {
  const response = await fetch("/api/backend/v1/users", {
    method: "POST",
    headers: jsonHeaders(input.actor_username),
    body: JSON.stringify({
      actor_username: input.actor_username,
      username: input.username,
      password: input.password,
      role: input.role,
      display_name: input.display_name || null,
      manager_id: input.manager_id,
      team_id: input.team_id,
      must_change_password: Boolean(input.must_change_password),
    }),
  });
  if (!response.ok) {
    throw new Error(`User create failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as UserMutationResponse;
}

export async function updateUserMutation(input: {
  actor_username: string;
  user_id: number;
  display_name?: string;
  role?: "admin" | "manager" | "member";
  manager_id?: number;
  team_id?: number;
  is_active?: boolean;
}): Promise<UserMutationResponse> {
  const response = await fetch(`/api/backend/v1/users/${input.user_id}`, {
    method: "PATCH",
    headers: jsonHeaders(input.actor_username),
    body: JSON.stringify({
      actor_username: input.actor_username,
      display_name: input.display_name,
      role: input.role,
      manager_id: input.manager_id,
      team_id: input.team_id,
      is_active: input.is_active,
    }),
  });
  if (!response.ok) {
    throw new Error(`User update failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as UserMutationResponse;
}

export async function resetUserPasswordMutation(input: {
  actor_username: string;
  user_id: number;
  new_password: string;
  require_change?: boolean;
}): Promise<UserPasswordResetResponse> {
  const response = await fetch(`/api/backend/v1/users/${input.user_id}/reset-password`, {
    method: "POST",
    headers: jsonHeaders(input.actor_username),
    body: JSON.stringify({
      actor_username: input.actor_username,
      new_password: input.new_password,
      require_change: Boolean(input.require_change),
    }),
  });
  if (!response.ok) {
    throw new Error(`Password reset failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as UserPasswordResetResponse;
}

export async function createTeamMutation(input: {
  actor_username: string;
  name: string;
  description?: string;
}): Promise<TeamMutationResponse> {
  const response = await fetch("/api/backend/v1/teams", {
    method: "POST",
    headers: jsonHeaders(input.actor_username),
    body: JSON.stringify({
      actor_username: input.actor_username,
      name: input.name,
      description: input.description || null,
    }),
  });
  if (!response.ok) {
    throw new Error(`Team create failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as TeamMutationResponse;
}

export async function updateTeamMutation(input: {
  actor_username: string;
  team_id: number;
  name?: string;
  description?: string;
}): Promise<TeamMutationResponse> {
  const response = await fetch(`/api/backend/v1/teams/${input.team_id}`, {
    method: "PATCH",
    headers: jsonHeaders(input.actor_username),
    body: JSON.stringify({
      actor_username: input.actor_username,
      name: input.name,
      description: input.description,
    }),
  });
  if (!response.ok) {
    throw new Error(`Team update failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as TeamMutationResponse;
}

export async function deleteTeamMutation(input: {
  actor_username: string;
  team_id: number;
}): Promise<TeamDeleteResponse> {
  const response = await fetch(`/api/backend/v1/teams/${input.team_id}`, {
    method: "DELETE",
    headers: jsonHeaders(input.actor_username),
  });
  if (!response.ok) {
    throw new Error(`Team delete failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as TeamDeleteResponse;
}

export async function readAdminAiHealth(input: {
  actor_username: string;
  live_probe?: boolean;
}): Promise<AdminAiHealthResponse> {
  const probeParam = input.live_probe ? "?live_probe=true" : "?live_probe=false";
  const response = await fetch(`/api/backend/v1/admin/ai-health${probeParam}`, {
    method: "GET",
    cache: "no-store",
    headers: jsonHeaders(input.actor_username),
  });
  if (!response.ok) {
    throw new Error(`AI health read failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as AdminAiHealthResponse;
}

export async function readAdminPdfHealth(input: {
  actor_username: string;
}): Promise<AdminPdfHealthResponse> {
  const response = await fetch("/api/backend/v1/admin/pdf-health", {
    method: "GET",
    cache: "no-store",
    headers: jsonHeaders(input.actor_username),
  });
  if (!response.ok) {
    throw new Error(`PDF health read failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as AdminPdfHealthResponse;
}

export async function readAdminDbBackup(input: {
  actor_username: string;
}): Promise<Blob> {
  const response = await fetch("/api/backend/v1/admin/db-backup", {
    method: "GET",
    cache: "no-store",
    headers: jsonHeaders(input.actor_username),
  });
  if (!response.ok) {
    throw new Error(`DB backup export failed: ${await responseDetail(response)}`);
  }
  return await response.blob();
}

export async function restoreAdminDbBackup(input: {
  actor_username: string;
  payload: Record<string, unknown>;
}): Promise<AdminDbRestoreResponse> {
  const response = await fetch("/api/backend/v1/admin/db-restore", {
    method: "POST",
    headers: jsonHeaders(input.actor_username),
    body: JSON.stringify(input.payload),
  });
  if (!response.ok) {
    throw new Error(`DB backup restore failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as AdminDbRestoreResponse;
}

export async function submitBackendJob(input: {
  actor_username: string;
  kind: "pdf.weekly" | "ai.generate_json";
  payload: Record<string, unknown>;
  max_attempts?: number;
}): Promise<AsyncJobView> {
  const response = await fetch("/api/backend/v1/jobs", {
    method: "POST",
    headers: jsonHeaders(input.actor_username),
    body: JSON.stringify({
      actor_username: input.actor_username,
      kind: input.kind,
      payload: input.payload,
      max_attempts: input.max_attempts ?? 2,
    }),
  });
  if (!response.ok) {
    throw new Error(`Job submit failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as AsyncJobView;
}

export async function readBackendJob(input: {
  actor_username: string;
  job_id: string;
}): Promise<AsyncJobView> {
  const response = await fetch(`/api/backend/v1/jobs/${encodeURIComponent(input.job_id)}`, {
    method: "GET",
    cache: "no-store",
    headers: jsonHeaders(input.actor_username),
  });
  if (!response.ok) {
    throw new Error(`Job read failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as AsyncJobView;
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

export async function deleteAlignmentMutation(input: {
  actor_username: string;
  edge_id: number;
}): Promise<AlignmentDeleteResponse> {
  const response = await fetch(`/api/backend/v1/alignments/${input.edge_id}`, {
    method: "DELETE",
    headers: jsonHeaders(input.actor_username),
  });
  if (!response.ok) {
    throw new Error(`Alignment delete failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as AlignmentDeleteResponse;
}
