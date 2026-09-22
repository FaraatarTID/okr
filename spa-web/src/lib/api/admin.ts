import { backendBlobRequest, backendJsonRequest } from "@/lib/api/http";
import type {
  AdminAiHealthResponse,
  AdminDbRestoreResponse,
  AdminPdfHealthResponse,
  AuditEventSummaryView,
  AuditSummaryBucketView,
  AuditSummaryView,
  TeamDeleteResponse,
  TeamMutationResponse,
  UserMutationResponse,
  UserPasswordResetResponse,
} from "@/lib/api/types";
import { readBackendQuery } from "@/lib/api/atlas";
import type { ReadQueryResponse } from "@/lib/api/backend-schema";

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function optionalNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function optionalText(value: unknown): string | null | undefined {
  return typeof value === "string" || value === null ? value : undefined;
}

function auditBuckets(value: unknown): AuditSummaryBucketView[] | undefined {
  if (!Array.isArray(value)) {
    return undefined;
  }
  return value.flatMap((entry) => {
    const bucket = asRecord(entry);
    const count = optionalNumber(bucket?.count);
    const bucketValue = bucket?.value;
    if (
      !bucket ||
      count === undefined ||
      !(
        typeof bucketValue === "string" ||
        typeof bucketValue === "number" ||
        bucketValue === null
      )
    ) {
      return [];
    }
    return [{ value: bucketValue, count }];
  });
}

function auditEvents(value: unknown): AuditEventSummaryView[] | undefined {
  if (!Array.isArray(value)) {
    return undefined;
  }
  return value.flatMap((entry) => {
    const event = asRecord(entry);
    const id = optionalNumber(event?.id);
    if (!event || id === undefined) {
      return [];
    }
    return [{
      id,
      actor: optionalText(event.actor),
      actor_user_id: optionalNumber(event.actor_user_id),
      actor_role: optionalText(event.actor_role),
      actor_team_id: optionalNumber(event.actor_team_id),
      action: optionalText(event.action),
      entity: optionalText(event.entity),
      result: optionalText(event.result),
      target_type: optionalText(event.target_type),
      target_id: optionalNumber(event.target_id),
      target_owner_id: optionalNumber(event.target_owner_id),
      target_team_id: optionalNumber(event.target_team_id),
      correlation_id: optionalText(event.correlation_id),
      request_id: optionalText(event.request_id),
      created_at: optionalText(event.created_at),
    }];
  });
}

/** Project the broad generated read-query contract into the admin screen model. */
export function toAuditSummaryView(payload: ReadQueryResponse): AuditSummaryView {
  return {
    window_days: optionalNumber(payload.window_days),
    recent_limit: optionalNumber(payload.recent_limit),
    total_events: optionalNumber(payload.total_events),
    success_events: optionalNumber(payload.success_events),
    failure_events: optionalNumber(payload.failure_events),
    latest_event_at: optionalText(payload.latest_event_at),
    by_actor_role: auditBuckets(payload.by_actor_role),
    by_actor_team_id: auditBuckets(payload.by_actor_team_id),
    by_target_type: auditBuckets(payload.by_target_type),
    by_entity: auditBuckets(payload.by_entity),
    by_action: auditBuckets(payload.by_action),
    recent_events: auditEvents(payload.recent_events),
  };
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
  return backendJsonRequest({
    operation: "api_create_user_v1_users_post",
    path: "/v1/users",
    actor: input.actor_username,
    label: "User create",
    body: {
      actor_username: input.actor_username,
      username: input.username,
      password: input.password,
      role: input.role,
      display_name: input.display_name || null,
      manager_id: input.manager_id,
      team_id: input.team_id,
      must_change_password: Boolean(input.must_change_password),
    },
  });
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
  return backendJsonRequest({
    operation: "api_update_user_v1_users__user_id__patch",
    path: `/v1/users/${input.user_id}`,
    actor: input.actor_username,
    label: "User update",
    body: {
      actor_username: input.actor_username,
      display_name: input.display_name,
      role: input.role,
      manager_id: input.manager_id,
      team_id: input.team_id,
      is_active: input.is_active,
    },
  });
}

export async function resetUserPasswordMutation(input: {
  actor_username: string;
  user_id: number;
  new_password: string;
  require_change?: boolean;
}): Promise<UserPasswordResetResponse> {
  return backendJsonRequest({
    operation: "api_reset_user_password_v1_users__user_id__reset_password_post",
    path: `/v1/users/${input.user_id}/reset-password`,
    actor: input.actor_username,
    label: "Password reset",
    body: {
      actor_username: input.actor_username,
      new_password: input.new_password,
      require_change: Boolean(input.require_change),
    },
  });
}

export async function createTeamMutation(input: {
  actor_username: string;
  name: string;
  description?: string;
}): Promise<TeamMutationResponse> {
  return backendJsonRequest({
    operation: "api_create_team_v1_teams_post",
    path: "/v1/teams",
    actor: input.actor_username,
    label: "Team create",
    body: {
      actor_username: input.actor_username,
      name: input.name,
      description: input.description || null,
    },
  });
}

export async function updateTeamMutation(input: {
  actor_username: string;
  team_id: number;
  name?: string;
  description?: string;
}): Promise<TeamMutationResponse> {
  return backendJsonRequest({
    operation: "api_update_team_v1_teams__team_id__patch",
    path: `/v1/teams/${input.team_id}`,
    actor: input.actor_username,
    label: "Team update",
    body: {
      actor_username: input.actor_username,
      name: input.name,
      description: input.description,
    },
  });
}

export async function deleteTeamMutation(input: {
  actor_username: string;
  team_id: number;
}): Promise<TeamDeleteResponse> {
  return backendJsonRequest({
    operation: "api_delete_team_v1_teams__team_id__delete",
    path: `/v1/teams/${input.team_id}`,
    actor: input.actor_username,
    label: "Team delete",
  });
}

export async function readAdminAiHealth(input: {
  actor_username: string;
  live_probe?: boolean;
}): Promise<AdminAiHealthResponse> {
  return backendJsonRequest({
    operation: "api_admin_ai_health_v1_admin_ai_health_get",
    path: "/v1/admin/ai-health",
    query: { live_probe: Boolean(input.live_probe) },
    actor: input.actor_username,
    label: "AI health read",
    cache: "no-store",
  });
}

export async function readAdminPdfHealth(input: {
  actor_username: string;
}): Promise<AdminPdfHealthResponse> {
  return backendJsonRequest({
    operation: "api_admin_pdf_health_v1_admin_pdf_health_get",
    path: "/v1/admin/pdf-health",
    actor: input.actor_username,
    label: "PDF health read",
    cache: "no-store",
  });
}

export async function readAuditSummary(input: {
  actor_username: string;
  days?: number;
  recent_limit?: number;
}): Promise<AuditSummaryView> {
  const payload = await readBackendQuery({
    actor_username: input.actor_username,
    kind: "audit.summary",
    params: {
      days: input.days,
      recent_limit: input.recent_limit,
    },
  });
  return toAuditSummaryView(payload);
}

export async function readAdminDbBackup(input: {
  actor_username: string;
}): Promise<Blob> {
  return backendBlobRequest({
    operation: "api_admin_db_backup_v1_admin_db_backup_get",
    path: "/v1/admin/db-backup",
    actor: input.actor_username,
    label: "DB backup export",
    cache: "no-store",
  });
}

export async function restoreAdminDbBackup(input: {
  actor_username: string;
  payload: { format: string } & Record<string, unknown>;
}): Promise<AdminDbRestoreResponse> {
  return backendJsonRequest({
    operation: "api_admin_db_restore_v1_admin_db_restore_post",
    path: "/v1/admin/db-restore",
    actor: input.actor_username,
    label: "DB backup restore",
    body: input.payload,
  });
}
