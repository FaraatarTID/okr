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

  // Forward the real client IP for backend rate limiting.
  // The backend trusts this header only when the service token is valid,
  // preventing direct spoofing by untrusted clients.
  const clientIp = firstHeaderValue(request.incomingHeaders["x-forwarded-for"])
    || firstHeaderValue(request.incomingHeaders["x-real-ip"])
    || "";

  const outboundHeaders: Record<string, string> = {
    accept: "application/json",
    "x-correlation-id": readCorrelationId(request.incomingHeaders),
    "x-request-id": readRequestId(request.incomingHeaders),
  };

  if (clientIp) {
    outboundHeaders["x-forwarded-for"] = clientIp;
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

  const securityHeaders = buildBackendSecurityHeaders({
    method,
    path,
    bodyBytes,
    serviceToken: config.backendServiceToken,
    signingSecret: config.backendSigningSecret,
  });
  Object.assign(outboundHeaders, securityHeaders);

  const backendUrl = new URL(`${path}${queryString}`, `${config.backendApiUrl}/`).toString();
  const timeoutMs = resolveTimeoutMs(path, config.requestTimeoutMs);
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
  };
}
