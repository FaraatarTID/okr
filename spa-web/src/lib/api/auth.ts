import { jsonHeaders, responseDetail } from "@/lib/api/http";

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

export interface SessionMeResponse {
  user: AuthUser;
}

export async function bffLogin(input: {
  username: string;
  password: string;
  client_ip?: string;
}): Promise<AuthResponse> {
  const response = await fetch("/api/session/login", {
    method: "POST",
    headers: jsonHeaders(),
    body: JSON.stringify(input),
    credentials: "same-origin",
  });
  if (!response.ok) {
    throw new Error(`Login failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as AuthResponse;
}

export async function readSessionUser(): Promise<AuthUser> {
  const response = await fetch("/api/session/me", {
    method: "GET",
    cache: "no-store",
    credentials: "same-origin",
  });
  if (!response.ok) {
    throw new Error(`Session lookup failed: ${await responseDetail(response)}`);
  }
  const payload = (await response.json()) as SessionMeResponse;
  if (!payload.user) {
    throw new Error("Session lookup failed: missing user payload.");
  }
  return payload.user;
}

export async function logoutSession(): Promise<void> {
  const response = await fetch("/api/session/logout", {
    method: "POST",
    credentials: "same-origin",
  });
  if (!response.ok) {
    throw new Error(`Session logout failed: ${await responseDetail(response)}`);
  }
}

/**
 * The only route that may render while `must_change_password` is set.
 *
 * The flag is enforced at the shell boundary so it cannot be bypassed by
 * navigating straight to an application route or by reloading after login. Both
 * the boundary that redirects and the page that renders the panel derive their
 * target from here so they cannot drift apart.
 */
export const FORCED_PASSWORD_CHANGE_PATH = "/login";

export const FORCED_PASSWORD_CHANGE_PARAM = "change_password";

/**
 * Build the location a user with a pending forced password change must be sent
 * to, preserving where they were so `return_to` can restore it afterwards.
 */
export function forcedPasswordChangeLocation(user: AuthUser, returnTo?: string): string {
  if (!user.must_change_password) {
    return returnTo && returnTo.startsWith("/") ? returnTo : "/";
  }
  const params = new URLSearchParams({ [FORCED_PASSWORD_CHANGE_PARAM]: "1" });
  if (returnTo && returnTo.startsWith("/") && !returnTo.startsWith("//")) {
    params.set("return_to", returnTo);
  }
  return `${FORCED_PASSWORD_CHANGE_PATH}?${params.toString()}`;
}
