import { createHmac, randomBytes, timingSafeEqual } from "node:crypto";

const SESSION_COOKIE_NAME = "okr_spa_session";
const CSRF_COOKIE_NAME = "okr_csrf_token";
const SESSION_VERSION = "v1";

export interface SessionUser {
  id: number;
  username: string;
  display_name: string;
  role: string;
  team_id?: number | null;
  manager_id?: number | null;
  must_change_password?: boolean;
  token_version?: number;
}

interface SessionPayload {
  v: string;
  iat: number;
  exp: number;
  user: SessionUser;
}

function base64UrlEncode(bytes: Buffer): string {
  return bytes
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
}

function base64UrlDecode(text: string): Buffer {
  const normalized = String(text || "").replace(/-/g, "+").replace(/_/g, "/");
  const padding = normalized.length % 4 === 0 ? "" : "=".repeat(4 - (normalized.length % 4));
  return Buffer.from(`${normalized}${padding}`, "base64");
}

function signatureForPayload(payloadB64: string, secret: string): string {
  return createHmac("sha256", secret).update(payloadB64).digest("hex");
}

export function issueSessionToken(input: {
  user: SessionUser;
  secret: string;
  nowEpochSeconds?: number;
  ttlSeconds: number;
}): string {
  const nowEpochSeconds =
    Number.isFinite(input.nowEpochSeconds) && Number(input.nowEpochSeconds) > 0
      ? Math.floor(Number(input.nowEpochSeconds))
      : Math.floor(Date.now() / 1000);

  const payload: SessionPayload = {
    v: SESSION_VERSION,
    iat: nowEpochSeconds,
    exp: nowEpochSeconds + Math.max(60, Math.floor(input.ttlSeconds)),
    user: input.user,
  };

  const payloadB64 = base64UrlEncode(Buffer.from(JSON.stringify(payload), "utf-8"));
  const signature = signatureForPayload(payloadB64, input.secret);
  return `${payloadB64}.${signature}`;
}

function normalizeSessionUser(value: unknown): SessionUser | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const user = value as Record<string, unknown>;
  const username = String(user.username ?? "").trim();
  const displayName = String(user.display_name ?? "").trim();
  const role = String(user.role ?? "").trim();
  const id = Number(user.id);
  if (!username || !displayName || !role || !Number.isFinite(id) || id <= 0) {
    return null;
  }
  return {
    id: Math.trunc(id),
    username,
    display_name: displayName,
    role,
    team_id: user.team_id == null ? null : Number(user.team_id),
    manager_id: user.manager_id == null ? null : Number(user.manager_id),
    must_change_password: Boolean(user.must_change_password),
    token_version: user.token_version == null ? undefined : Number(user.token_version),
  };
}

export function verifySessionToken(input: {
  token: string;
  secret: string;
  nowEpochSeconds?: number;
}): SessionUser | null {
  const rawToken = String(input.token || "").trim();
  if (!rawToken) {
    return null;
  }
  const separator = rawToken.indexOf(".");
  if (separator <= 0 || separator >= rawToken.length - 1) {
    return null;
  }

  const payloadB64 = rawToken.slice(0, separator);
  const signatureHex = rawToken.slice(separator + 1).toLowerCase();
  if (!/^[a-f0-9]{64}$/.test(signatureHex)) {
    return null;
  }

  const expectedHex = signatureForPayload(payloadB64, input.secret).toLowerCase();
  const supplied = Buffer.from(signatureHex, "utf-8");
  const expected = Buffer.from(expectedHex, "utf-8");
  if (supplied.length !== expected.length || !timingSafeEqual(supplied, expected)) {
    return null;
  }

  let decoded: unknown;
  try {
    decoded = JSON.parse(base64UrlDecode(payloadB64).toString("utf-8"));
  } catch {
    return null;
  }
  if (!decoded || typeof decoded !== "object") {
    return null;
  }
  const payload = decoded as Record<string, unknown>;
  if (String(payload.v ?? "") !== SESSION_VERSION) {
    return null;
  }
  const exp = Number(payload.exp);
  const nowEpochSeconds =
    Number.isFinite(input.nowEpochSeconds) && Number(input.nowEpochSeconds) > 0
      ? Math.floor(Number(input.nowEpochSeconds))
      : Math.floor(Date.now() / 1000);
  if (!Number.isFinite(exp) || exp < nowEpochSeconds) {
    return null;
  }

  return normalizeSessionUser(payload.user);
}

export function parseCookieHeader(rawHeader: string | undefined): Record<string, string> {
  const parsed: Record<string, string> = {};
  const text = String(rawHeader || "").trim();
  if (!text) {
    return parsed;
  }
  for (const part of text.split(";")) {
    const segment = String(part).trim();
    if (!segment) {
      continue;
    }
    const index = segment.indexOf("=");
    if (index <= 0) {
      continue;
    }
    const key = segment.slice(0, index).trim();
    const rawValue = segment.slice(index + 1).trim();
    if (!key) {
      continue;
    }
    try {
      parsed[key] = decodeURIComponent(rawValue);
    } catch {
      // Skip malformed percent-encoding — treat cookie as absent
    }
  }
  return parsed;
}

export function readSessionUserFromCookie(input: {
  cookieHeader: string | undefined;
  secret: string;
}): SessionUser | null {
  const cookies = parseCookieHeader(input.cookieHeader);
  const token = String(cookies[SESSION_COOKIE_NAME] || "").trim();
  if (!token) {
    return null;
  }
  return verifySessionToken({
    token,
    secret: input.secret,
  });
}

export function issueSessionCookie(input: {
  token: string;
  ttlSeconds: number;
  secure: boolean;
}): string {
  const parts = [
    `${SESSION_COOKIE_NAME}=${encodeURIComponent(input.token)}`,
    "Path=/",
    "HttpOnly",
    "SameSite=Lax",
    `Max-Age=${Math.max(60, Math.floor(input.ttlSeconds))}`,
  ];
  if (input.secure) {
    parts.push("Secure");
  }
  return parts.join("; ");
}

export function clearSessionCookie(input: { secure: boolean }): string {
  const parts = [
    `${SESSION_COOKIE_NAME}=`,
    "Path=/",
    "HttpOnly",
    "SameSite=Lax",
    "Max-Age=0",
    "Expires=Thu, 01 Jan 1970 00:00:00 GMT",
  ];
  if (input.secure) {
    parts.push("Secure");
  }
  return parts.join("; ");
}

// --- CSRF Double-Submit Cookie Protection ---

export function generateCsrfToken(): string {
  return randomBytes(32).toString("hex");
}

export function issueCsrfCookie(input: {
  token: string;
  ttlSeconds: number;
  secure: boolean;
}): string {
  const parts = [
    `${CSRF_COOKIE_NAME}=${encodeURIComponent(input.token)}`,
    "Path=/",
    // Intentionally NOT HttpOnly — JavaScript must read this to send as header
    "SameSite=Strict",
    `Max-Age=${Math.max(60, Math.floor(input.ttlSeconds))}`,
  ];
  if (input.secure) {
    parts.push("Secure");
  }
  return parts.join("; ");
}

export function clearCsrfCookie(input: { secure: boolean }): string {
  const parts = [
    `${CSRF_COOKIE_NAME}=`,
    "Path=/",
    "SameSite=Strict",
    "Max-Age=0",
    "Expires=Thu, 01 Jan 1970 00:00:00 GMT",
  ];
  if (input.secure) {
    parts.push("Secure");
  }
  return parts.join("; ");
}

export function readCsrfTokenFromCookie(cookieHeader: string | undefined): string {
  const cookies = parseCookieHeader(cookieHeader);
  return String(cookies[CSRF_COOKIE_NAME] || "").trim();
}

export function validateCsrfToken(input: {
  cookieHeader: string | undefined;
  headerValue: string | string[] | undefined;
}): boolean {
  const cookieToken = readCsrfTokenFromCookie(input.cookieHeader);
  if (!cookieToken) {
    return false;
  }
  const headerToken = String(
    Array.isArray(input.headerValue) ? input.headerValue[0] : input.headerValue || "",
  ).trim();
  if (!headerToken) {
    return false;
  }
  // Timing-safe comparison to prevent timing attacks
  const a = Buffer.from(cookieToken, "utf-8");
  const b = Buffer.from(headerToken, "utf-8");
  if (a.length !== b.length) {
    return false;
  }
  return timingSafeEqual(a, b);
}
