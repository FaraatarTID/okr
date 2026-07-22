import { jsonHeaders, responseDetail } from "@/lib/api/http";
import type {
  AdminAiHealthResponse,
  AdminDbRestoreResponse,
  AdminPdfHealthResponse,
  AuditSummaryResponse,
  TeamDeleteResponse,
  TeamMutationResponse,
  UserMutationResponse,
  UserPasswordResetResponse,
} from "@/lib/api/types";
import { readBackendQuery } from "@/lib/api/atlas";

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
    headers: jsonHeaders(input.actor_username, false),
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

export async function readAuditSummary(input: {
  actor_username: string;
  days?: number;
  recent_limit?: number;
}): Promise<AuditSummaryResponse> {
  const payload = await readBackendQuery({
    actor_username: input.actor_username,
    kind: "audit.summary",
    params: {
      days: input.days,
      recent_limit: input.recent_limit,
    },
  });
  return payload as AuditSummaryResponse;
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
