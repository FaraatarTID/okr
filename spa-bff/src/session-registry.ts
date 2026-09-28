import type { BffConfig } from "./config.js";
import { buildBackendSecurityHeaders } from "./signing.js";

type RegistryAction = "register" | "revoke";

export class SessionRegistryUnavailableError extends Error {
  constructor(readonly statusCode?: number) {
    super("Backend session registry could not confirm the operation.");
    this.name = "SessionRegistryUnavailableError";
  }
}

async function callRegistry(
  config: BffConfig,
  action: RegistryAction,
  body: Record<string, unknown>,
  fetchFn: typeof fetch = globalThis.fetch,
): Promise<void> {
  const method = "POST";
  const path = `/v1/internal/session-registry/${action}`;
  const bodyBytes = new TextEncoder().encode(JSON.stringify(body));
  const headers = buildBackendSecurityHeaders({
    method,
    path,
    bodyBytes,
    serviceToken: config.backendServiceToken,
    signingSecret: config.backendSigningSecret,
    signingKeyId: config.backendSigningKeyId,
  });
  if (
    !headers["x-okr-service-token"] ||
    !headers["x-okr-signature"] ||
    !headers["x-okr-timestamp"] ||
    !headers["x-okr-nonce"]
  ) {
    throw new SessionRegistryUnavailableError();
  }

  let response: Response;
  try {
    response = await fetchFn(`${config.backendApiUrl}${path}`, {
      method,
      headers: { ...headers, "content-type": "application/json" },
      body: Buffer.from(bodyBytes),
      signal: AbortSignal.timeout(config.requestTimeoutMs),
    });
  } catch {
    throw new SessionRegistryUnavailableError();
  }
  if (!response.ok) {
    throw new SessionRegistryUnavailableError(response.status);
  }
  let acknowledgement: unknown;
  try {
    acknowledgement = await response.json();
  } catch {
    throw new SessionRegistryUnavailableError(response.status);
  }
  const expectedStatus = action === "register" ? "registered" : "revoked";
  if (
    !acknowledgement ||
    typeof acknowledgement !== "object" ||
    (acknowledgement as Record<string, unknown>).status !== expectedStatus
  ) {
    throw new SessionRegistryUnavailableError(response.status);
  }
}

export function registerBackendSession(
  config: BffConfig,
  input: { sessionId: string; actorId: number; expiresAtEpochSeconds: number },
  fetchFn?: typeof fetch,
): Promise<void> {
  return callRegistry(
    config,
    "register",
    {
      session_id: input.sessionId,
      actor_id: input.actorId,
      expires_at: new Date(input.expiresAtEpochSeconds * 1000).toISOString(),
    },
    fetchFn,
  );
}

export function revokeBackendSession(
  config: BffConfig,
  sessionId: string,
  fetchFn?: typeof fetch,
): Promise<void> {
  return callRegistry(config, "revoke", { session_id: sessionId }, fetchFn);
}
