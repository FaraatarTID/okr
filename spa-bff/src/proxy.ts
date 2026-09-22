import { randomUUID } from "node:crypto";

import type { BffConfig } from "./config.js";
import { buildBackendSecurityHeaders } from "./signing.js";

export interface ProxyRequest {
  method: string;
  path: string;
  queryString: string;
  body: unknown;
  actor: string | null;
  incomingHeaders: Record<string, string | string[] | undefined>;
}

export interface ProxyResult {
  status: number;
  headers: Headers;
  body: Buffer;
  upstreamDurationMs: number;
}

function firstHeaderValue(raw: string | string[] | undefined): string {
  if (Array.isArray(raw)) {
    return String(raw[0] ?? "").trim();
  }
  return String(raw ?? "").trim();
}

function readCorrelationId(headers: Record<string, string | string[] | undefined>): string {
  return (
    firstHeaderValue(headers["x-correlation-id"]) ||
    firstHeaderValue(headers["x-okr-correlation-id"]) ||
    randomUUID()
  );
}

function readRequestId(headers: Record<string, string | string[] | undefined>): string {
  return (
    firstHeaderValue(headers["x-request-id"]) ||
    firstHeaderValue(headers["x-okr-request-id"]) ||
    randomUUID()
  );
}

function encodeJsonBody(body: unknown, method: string): Uint8Array | null {
  const normalizedMethod = String(method || "").toUpperCase();
  if (normalizedMethod === "GET" || normalizedMethod === "DELETE") {
    return null;
  }
  if (body === undefined) {
    return null;
  }
  return new TextEncoder().encode(JSON.stringify(body));
}

function resolveTimeoutMs(path: string, defaultTimeoutMs: number): number {
  const normalized = String(path || "").trim().toLowerCase();
  if (
    normalized.startsWith("/v1/read/atlas/snapshot") ||
    normalized.startsWith("/v1/read/leadership/metrics")
  ) {
    return Math.max(defaultTimeoutMs, 90_000);
  }
  // Check-In and other workspace views fan out into several Supabase-backed
  // read queries; free-tier wake-up and pooler latency can exceed 20 seconds.
  if (normalized.startsWith("/v1/read/query")) {
    return Math.max(defaultTimeoutMs, 120_000);
  }
  // AI analysis calls the external provider synchronously; free-tier providers
  // can take well over 30s per node.
  if (normalized.startsWith("/v1/ai/")) {
    return Math.max(defaultTimeoutMs, 120_000);
  }
  if (normalized.startsWith("/v1/jobs")) {
    return Math.max(defaultTimeoutMs, 120_000);
  }
  return defaultTimeoutMs;
}

export async function proxyToBackend(
  config: BffConfig,
  request: ProxyRequest,
  deps?: { fetchFn?: typeof fetch },
): Promise<ProxyResult> {
  const fetchFn = deps?.fetchFn ?? fetch;
  const method = String(request.method || "").toUpperCase();
  const path = String(request.path || "").trim();
  const queryString = String(request.queryString || "").trim();
  const bodyBytes = encodeJsonBody(request.body, method);
  const actor = String(request.actor || "").trim();
  const idempotencyKey = firstHeaderValue(
    request.incomingHeaders["x-okr-idempotency-key"],
  );
  const tokenVersion = firstHeaderValue(
    request.incomingHeaders["x-okr-token-version"],
  );
  const sessionRole = firstHeaderValue(request.incomingHeaders["x-okr-role"]);
  const sessionRoles = firstHeaderValue(request.incomingHeaders["x-okr-roles"]);
  // Content negotiation belongs to the documented backend operation. Preserve
  // the browser's safe Accept preference so binary downloads do not become
  // impossible through the BFF; JSON remains the safe default for callers
  // that omit it.
  const accept = firstHeaderValue(request.incomingHeaders.accept) || "application/json";

  // Forward the client IP for backend rate limiting and login throttling.
  //
  // The value comes from the private, always-overwritten X-OKR-Client-IP header set
  // by our edge. X-Forwarded-For and X-Real-IP are deliberately NOT used: nginx sets
  // X-Forwarded-For with $proxy_add_x_forwarded_for, which APPENDS to whatever the
  // client sent, so its leftmost entry is caller-controlled - keying a control on it
  // let the caller choose its own key. The backend honours this header only when the
  // service token is valid. See docs/client-ip-trust-adr.md.
  const clientIp = firstHeaderValue(request.incomingHeaders["x-okr-client-ip"]) || "";

  const outboundHeaders: Record<string, string> = {
    accept,
    "x-correlation-id": readCorrelationId(request.incomingHeaders),
    "x-request-id": readRequestId(request.incomingHeaders),
  };

  if (clientIp) {
    outboundHeaders["x-okr-client-ip"] = clientIp;
  }

  if (bodyBytes) {
    outboundHeaders["content-type"] = "application/json";
  }
  if (actor) {
    outboundHeaders["x-okr-actor"] = actor;
  }
  if (idempotencyKey) {
    outboundHeaders["x-okr-idempotency-key"] = idempotencyKey;
  }
  if (tokenVersion) {
    outboundHeaders["x-okr-token-version"] = tokenVersion;
  }
  if (sessionRole) {
    outboundHeaders["x-okr-role"] = sessionRole;
  }
  if (sessionRoles) {
    outboundHeaders["x-okr-roles"] = sessionRoles;
  }

  const securityHeaders = buildBackendSecurityHeaders({
    method,
    path,
    bodyBytes,
    serviceToken: config.backendServiceToken,
    signingSecret: config.backendSigningSecret,
    signingKeyId: config.backendSigningKeyId,
  });
  Object.assign(outboundHeaders, securityHeaders);

  const backendUrl = new URL(`${path}${queryString}`, `${config.backendApiUrl}/`).toString();
  const timeoutMs = resolveTimeoutMs(path, config.requestTimeoutMs);
  const upstreamStartedAt = performance.now();
  const response = await fetchFn(backendUrl, {
    method,
    headers: outboundHeaders,
    body: bodyBytes ? Buffer.from(bodyBytes) : undefined,
    signal: AbortSignal.timeout(timeoutMs),
  });

  const arrayBuffer = await response.arrayBuffer();
  return {
    status: response.status,
    headers: response.headers,
    body: Buffer.from(arrayBuffer),
    upstreamDurationMs: Math.max(0, performance.now() - upstreamStartedAt),
  };
}
