import { createHash, createHmac, randomBytes } from "node:crypto";

export interface BackendSecurityHeaderInput {
  method: string;
  path: string;
  bodyBytes: Uint8Array | null;
  serviceToken: string;
  signingSecret: string;
  signingKeyId?: string;
  nowEpochSeconds?: number;
  nonce?: string;
  sessionId?: string;
  sessionActor?: string;
}

export function bodyDigestHex(bodyBytes: Uint8Array | null): string {
  const hash = createHash("sha256");
  if (bodyBytes && bodyBytes.length > 0) {
    hash.update(bodyBytes);
  }
  return hash.digest("hex");
}

export function canonicalSigningPayload(input: {
  method: string;
  path: string;
  timestamp: string;
  nonce: string;
  bodyDigest: string;
  sessionId?: string;
  sessionActor?: string;
}): string {
  const parts = [
    String(input.method || "").trim().toUpperCase(),
    String(input.path || "/").trim() || "/",
    String(input.timestamp || "").trim(),
    String(input.nonce || "").trim(),
    String(input.bodyDigest || "").trim(),
  ];
  if (input.sessionId !== undefined || input.sessionActor !== undefined) {
    const sessionId = input.sessionId === undefined
      ? "-"
      : Buffer.from(String(input.sessionId), "utf-8").toString("hex");
    const sessionActor = input.sessionActor === undefined
      ? "-"
      : Buffer.from(String(input.sessionActor), "utf-8").toString("hex");
    parts.push(`session_id:${sessionId}`, `session_actor:${sessionActor}`);
  }
  return parts.join("\n");
}

export function requestSignatureHex(input: {
  method: string;
  path: string;
  timestamp: string;
  nonce: string;
  bodyBytes: Uint8Array | null;
  signingSecret: string;
  sessionId?: string;
  sessionActor?: string;
}): string {
  const payload = canonicalSigningPayload({
    method: input.method,
    path: input.path,
    timestamp: input.timestamp,
    nonce: input.nonce,
    bodyDigest: bodyDigestHex(input.bodyBytes),
    sessionId: input.sessionId,
    sessionActor: input.sessionActor,
  });

  return createHmac("sha256", String(input.signingSecret))
    .update(payload)
    .digest("hex");
}

export function buildBackendSecurityHeaders(
  input: BackendSecurityHeaderInput,
): Record<string, string> {
  const headers: Record<string, string> = {
    "x-okr-service-token": String(input.serviceToken || "").trim(),
  };

  const signingSecret = String(input.signingSecret || "").trim();
  if (!signingSecret) {
    return headers;
  }

  const nowEpochSeconds =
    Number.isFinite(input.nowEpochSeconds) && Number(input.nowEpochSeconds) > 0
      ? Math.floor(Number(input.nowEpochSeconds))
      : Math.floor(Date.now() / 1000);
  const timestamp = String(nowEpochSeconds);
  const nonce = String(input.nonce || randomBytes(16).toString("hex")).trim();
  const signature = requestSignatureHex({
    method: input.method,
    path: input.path,
    timestamp,
    nonce,
    bodyBytes: input.bodyBytes,
    signingSecret,
    sessionId: input.sessionId,
    sessionActor: input.sessionActor,
  });

  headers["x-okr-timestamp"] = timestamp;
  headers["x-okr-nonce"] = nonce;
  headers["x-okr-signature"] = signature;
  const keyId = String(input.signingKeyId || "").trim();
  if (keyId) {
    headers["x-okr-key-id"] = keyId;
  }
  return headers;
}

