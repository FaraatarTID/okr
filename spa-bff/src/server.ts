import Fastify, { type FastifyReply, type FastifyRequest } from "fastify";
import { randomUUID } from "node:crypto";
import { pathToFileURL } from "node:url";

import { isAllowlistedRoute, normalizeBackendPath, requiresActorHeader, resolveAllowlistedOperation } from "./allowlist.js";
import type { BffConfig } from "./config.js";
import { DEFAULT_RATE_LIMIT, readConfig } from "./config.js";
import { proxyToBackend } from "./proxy.js";
import {
  FixedWindowLimiter,
  classifyRateLimitBucket,
  resolveRateLimitKey,
} from "./rate-limit.js";
import { buildBackendSecurityHeaders } from "./signing.js";
import type { BackendLoginResponse, BackendSessionResponse } from "./backend-schema.js";
import {
  clearSessionCookie,
  clearCsrfCookie,
  createSessionCredential,
  generateCsrfToken,
  issueCsrfCookie,
  issueSessionCookie,
  normalizeSessionUser,
  readSessionCredentialFromCookie,
  validateCsrfToken,
  type SessionCredential,
  type SessionUser,
} from "./session.js";
import {
  registerBackendSession,
  revokeBackendSession,
} from "./session-registry.js";

type WildcardParams = { "*": string };

/**
 * Request body ceilings, enforced by Fastify before a handler runs.
 *
 * Every JSON route this BFF proxies carries a small body: the backend schemas cap text
 * fields at 10 KB or less and lists at 200 entries, and the largest legitimate payload
 * (the team-coach `team_data` progress list) stays far below 1 MiB. So the default is
 * tight. The single exception is the operator database restore, which carries a whole
 * backup; it is disabled by default and blocked in production, so a large body there is
 * a non-production drill. The backend's own restore size check cannot bound this: it runs
 * after FastAPI has already parsed the whole body. This ceiling is the effective bound.
 */
export const DEFAULT_BODY_LIMIT_BYTES = 1024 * 1024;
export const DB_RESTORE_BODY_LIMIT_BYTES = 50 * 1024 * 1024;
const DB_RESTORE_WILDCARD_PATH = "v1/admin/db-restore";

const RESPONSE_HEADER_BLOCKLIST = new Set([
  "connection",
  "content-length",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

function appendUpstreamServerTiming(
  reply: { header: (name: string, value: string) => unknown },
  result: { headers: Headers; upstreamDurationMs: number },
  method: string,
  path: string,
): void {
  if (
    !new Set(["GET", "HEAD"]).has(method.toUpperCase())
    && !path.startsWith("/api/backend/v1/read/")
  ) {
    return;
  }
  const existing = result.headers.get("server-timing");
  const value = `bff-upstream;dur=${Math.max(0, result.upstreamDurationMs).toFixed(3)}`;
  reply.header("Server-Timing", existing ? `${existing}, ${value}` : value);
}

function readRequestId(headers: Record<string, string | string[] | undefined>): string {
  return (
    firstHeaderValue(headers["x-request-id"]) ||
    firstHeaderValue(headers["x-okr-request-id"]) ||
    randomUUID()
  );
}

function readCorrelationId(headers: Record<string, string | string[] | undefined>): string {
  return (
    firstHeaderValue(headers["x-correlation-id"]) ||
    firstHeaderValue(headers["x-okr-correlation-id"]) ||
    readRequestId(headers)
  );
}

function buildErrorEnvelope(
  code: string,
  message: string,
  requestId: string,
  extras?: Record<string, unknown>,
): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    code,
    error: message,
    message,
    request_id: requestId,
  };
  if (extras && Object.keys(extras).length > 0) {
    Object.assign(payload, extras);
  }
  return payload;
}

function buildBackendErrorEnvelope(
  statusCode: number,
  body: Buffer,
  requestId: string,
): Record<string, unknown> {
  const fallbackMessage = `Backend returned ${statusCode}.`;
  if (!body.length) {
    return buildErrorEnvelope(`HTTP_${statusCode}`, fallbackMessage, requestId);
  }

  try {
    const parsed = JSON.parse(body.toString("utf-8")) as Record<string, unknown>;
    const detail = typeof parsed["detail"] === "string" ? String(parsed["detail"]) : "";
    const message =
      typeof parsed["message"] === "string" && parsed["message"]
        ? String(parsed["message"])
        : detail
          ? detail
          : typeof parsed["error"] === "string" && parsed["error"]
            ? String(parsed["error"])
            : fallbackMessage;
    const code = typeof parsed["error_code"] === "string" && parsed["error_code"]
      ? String(parsed["error_code"])
      : `HTTP_${statusCode}`;
    return buildErrorEnvelope(code, message, requestId, parsed);
  } catch {
    return buildErrorEnvelope(`HTTP_${statusCode}`, fallbackMessage, requestId, {
      body: body.toString("utf-8"),
    });
  }
}

function buildBffLogPayload(
  event: string,
  request: { method: string; url: string },
  status: number,
  opts?: Record<string, unknown>,
): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    event,
    method: request.method,
    route: request.url,
    status,
    ts: new Date().toISOString(),
    ...opts,
  };
  return payload;
}

type BffRequestState = {
  _okrStartTs?: number;
  _okrCorrelationId?: string;
  _okrRequestId?: string;
};

function firstHeaderValue(raw: string | string[] | undefined): string {
  if (Array.isArray(raw)) {
    return String(raw[0] ?? "").trim();
  }
  return String(raw ?? "").trim();
}

function readSessionCredentialFromRequest(
  config: BffConfig,
  headers: Record<string, string | string[] | undefined>,
): SessionCredential | null {
  return readSessionCredentialFromCookie({
    cookieHeader: firstHeaderValue(headers.cookie),
    secret: config.sessionSecret,
  });
}

async function fetchFreshSessionUser(
  config: BffConfig,
  credential: SessionCredential,
  fetchFn: typeof fetch = globalThis.fetch,
): Promise<SessionUser> {
  const sessionUser = credential.user;
  const headers: Record<string, string> = {
    "x-okr-actor": sessionUser.username,
    "x-okr-session-id": credential.sessionId,
    "x-okr-session-actor": String(sessionUser.id),
    "x-okr-service-token": config.backendServiceToken,
  };
  if (Number.isSafeInteger(sessionUser.token_version) && (sessionUser.token_version ?? 0) > 0) {
    headers["x-okr-token-version"] = String(sessionUser.token_version);
  }
  // The backend enforces HMAC request signing in production; this direct call
  // bypasses proxyToBackend, so sign it here as well.
  Object.assign(
    headers,
    buildBackendSecurityHeaders({
      method: "GET",
      path: "/v1/auth/me",
      serviceToken: config.backendServiceToken,
      signingSecret: config.backendSigningSecret,
      signingKeyId: config.backendSigningKeyId,
      bodyBytes: null,
      sessionId: credential.sessionId,
      sessionActor: String(sessionUser.id),
    }),
  );
  const response = await fetchFn(`${config.backendApiUrl}/v1/auth/me`, {
    method: "GET",
    headers,
    // Session validation hits Supabase (multi-round-trip scope resolution);
    // give it the full proxy budget rather than a tight 5s cap.
    signal: AbortSignal.timeout(config.requestTimeoutMs),
  });
  if (!response.ok) {
    throw new BackendSessionValidationError(response.status);
  }
  const data = (await response.json()) as BackendSessionResponse;
  const user = normalizeSessionUser(data);
  if (!user) {
    throw new Error("Backend returned invalid user data.");
  }
  return user;
}

class BackendSessionValidationError extends Error {
  constructor(readonly statusCode: number) {
    super(`Backend session validation failed: ${statusCode}`);
    this.name = "BackendSessionValidationError";
  }
}

export function createServer(
  config: BffConfig,
  deps?: { fetchFn?: typeof fetch },
) {
  const app = Fastify({
    logger: {
      level: process.env.BFF_LOG_LEVEL || "info",
    },
    trustProxy: true,
    bodyLimit: DEFAULT_BODY_LIMIT_BYTES,
  });

  // Security headers on every response
  app.addHook("onSend", async (_request, reply) => {
    reply.header("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload");
    reply.header("X-Frame-Options", "DENY");
    reply.header("X-Content-Type-Options", "nosniff");
    reply.header("Referrer-Policy", "strict-origin-when-cross-origin");
    reply.header("Permissions-Policy", "camera=(), microphone=(), geolocation=()");
  });

  app.addHook("onRequest", async (request) => {
    const state = request as BffRequestState & typeof request;
    state._okrStartTs = Date.now();
    state._okrRequestId = readRequestId(request.headers);
    state._okrCorrelationId = firstHeaderValue(request.headers["x-correlation-id"])
      || firstHeaderValue(request.headers["x-okr-correlation-id"])
      || state._okrRequestId;
  });

  // Coarse flood backstop; see rate-limit.ts for what it does and does not guarantee.
  // Runs on `onRequest`, so a refused request costs no body parse and no backend hop.
  const rateLimit = config.rateLimit ?? DEFAULT_RATE_LIMIT;
  const windowMs = rateLimit.windowSeconds * 1000;
  const limiters = {
    login: new FixedWindowLimiter({ max: rateLimit.loginMax, windowMs }, rateLimit.maxKeys),
    session: new FixedWindowLimiter({ max: rateLimit.sessionMax, windowMs }, rateLimit.maxKeys),
  };
  app.addHook("onRequest", async (request, reply) => {
    const bucket = classifyRateLimitBucket(request.method, request.url);
    if (!bucket) {
      return;
    }
    // `request.ip` is deliberately not used: with `trustProxy` it comes from
    // X-Forwarded-For, which the caller controls (docs/client-ip-trust-adr.md).
    const key = resolveRateLimitKey(
      firstHeaderValue(request.headers["x-okr-client-ip"]),
      request.socket.remoteAddress,
    );
    const decision = limiters[bucket].consume(`${bucket}:${key}`);
    if (decision.allowed) {
      return;
    }
    const state = request as BffRequestState & typeof request;
    const requestId = state._okrRequestId || readRequestId(request.headers);
    app.log.warn(
      buildBffLogPayload("bff_rate_limited", request, 429, {
        request_id: requestId,
        bucket,
        client_key: key,
        retry_after_seconds: decision.retryAfterSeconds,
      }),
    );
    reply.header("Retry-After", String(decision.retryAfterSeconds));
    return reply.code(429).send(
      buildErrorEnvelope("RATE_LIMITED", "Too many requests. Retry shortly.", requestId, {
        retry_after_seconds: decision.retryAfterSeconds,
      }),
    );
  });

  app.addHook("onResponse", async (request, reply) => {
    const state = request as BffRequestState & typeof request;
    const durationMs = Date.now() - (state._okrStartTs ?? Date.now());
    const requestId = state._okrRequestId || readRequestId(request.headers);
    const correlationId = state._okrCorrelationId || readCorrelationId(request.headers);
    app.log.info(
      buildBffLogPayload(
        "bff_request_completed",
        request,
        reply.statusCode,
        {
          request_id: requestId,
          correlation_id: correlationId,
          actor: firstHeaderValue(request.headers["x-okr-actor"]),
          duration_ms: durationMs,
        },
      ),
    );
  });

  app.setErrorHandler((error, request, reply) => {
    const state = request as BffRequestState & typeof request;
    const errorName = error instanceof Error ? error.name : "Error";
    const errorMessage = error instanceof Error ? error.message : String(error);
    const requestId = state._okrRequestId || readRequestId(request.headers);
    const correlationId = state._okrCorrelationId || readCorrelationId(request.headers);

    // Fastify reports a client fault (oversize body, malformed JSON, unsupported media
    // type) as an error carrying a 4xx status. Answering those with a 500 would blame the
    // server for the caller's mistake and hide what to fix, so they keep their own status.
    const rawStatus = (error as { statusCode?: unknown } | null)?.statusCode;
    const clientStatus =
      typeof rawStatus === "number" && rawStatus >= 400 && rawStatus < 500 ? rawStatus : null;
    if (clientStatus !== null) {
      app.log.warn(
        buildBffLogPayload("bff_client_error", request, clientStatus, {
          request_id: requestId,
          correlation_id: correlationId,
          error_type: errorName,
          error_code: (error as { code?: unknown }).code,
        }),
      );
      const isTooLarge = clientStatus === 413;
      reply.code(clientStatus).send(
        buildErrorEnvelope(
          isTooLarge ? "PAYLOAD_TOO_LARGE" : `HTTP_${clientStatus}`,
          isTooLarge ? "Request body is too large." : "The request could not be processed.",
          requestId,
        ),
      );
      return;
    }

    app.log.error(
      buildBffLogPayload(
        "bff_unhandled_error",
        request,
        500,
        {
          request_id: requestId,
          correlation_id: correlationId,
          error_code: "BFF_UNHANDLED_ERROR",
          error_type: errorName,
          error_message: errorMessage,
        },
      ),
    );
    reply.code(500).send(
      buildErrorEnvelope(
        "BFF_UNHANDLED_ERROR",
        "BFF request failed unexpectedly.",
        requestId,
      ),
    );
  });

  app.get("/healthz", async () => {
    return {
      status: "ok",
      service: "spa-bff",
    };
  });

  app.post("/session/login", async (request, reply) => {
    const requestId = readRequestId(request.headers);
    try {
      const result = await proxyToBackend(
        config,
        {
          method: "POST",
          path: "/v1/auth/login",
          queryString: "",
          body: request.body,
          actor: null,
          incomingHeaders: request.headers,
        },
        deps,
      );
      if (result.status < 200 || result.status >= 300) {
        for (const [headerName, headerValue] of result.headers.entries()) {
          if (RESPONSE_HEADER_BLOCKLIST.has(headerName.toLowerCase())) {
            continue;
          }
          reply.header(headerName, headerValue);
        }
        reply.code(result.status);
        if (result.body.length === 0) {
          return reply.send(
            buildBackendErrorEnvelope(result.status, Buffer.alloc(0), requestId),
          );
        }
        if (result.status >= 400) {
          return reply.send(buildBackendErrorEnvelope(result.status, result.body, requestId));
        }
        return reply.send(result.body);
      }

      let payload: unknown;
      try {
        payload = JSON.parse(result.body.toString("utf-8"));
      } catch {
        return reply.code(502).send(
          buildErrorEnvelope(
            "BACKEND_RESPONSE_PARSE_ERROR",
            "Backend login response could not be parsed.",
            requestId,
          ),
        );
      }

      const payloadRecord =
        payload && typeof payload === "object"
          ? (payload as BackendLoginResponse)
          : ({} as BackendLoginResponse);
      const loginSuccess = Boolean(payloadRecord.success);
      const user = normalizeSessionUser(payloadRecord.user);
      if (!loginSuccess || !user) {
        const detail = String(payloadRecord.detail ?? "").trim();
        const errorCode = String(payloadRecord.error_code ?? "").trim();
        const message =
          detail ||
          (errorCode ? `Login failed: ${errorCode}` : "Invalid username or password.");
        return reply.code(401).send({
          ...buildErrorEnvelope(
            errorCode || "INVALID_CREDENTIALS",
            message,
            requestId,
            { success: false, error_code: errorCode || "INVALID_CREDENTIALS", detail: message },
          ),
        });
      }

      const credential = createSessionCredential({
        user,
        secret: config.sessionSecret,
        ttlSeconds: config.sessionTtlSeconds,
      });
      try {
        await registerBackendSession(
          config,
          {
            sessionId: credential.sessionId,
            actorId: user.id,
            expiresAtEpochSeconds: credential.expiresAtEpochSeconds,
          },
          deps?.fetchFn,
        );
      } catch {
        app.log.warn(
          buildBffLogPayload("bff_session_registration_failed", request, 503, {
            request_id: requestId,
            error_code: "SESSION_REGISTRY_UNAVAILABLE",
          }),
        );
        return reply.code(503).send(
          buildErrorEnvelope(
            "SESSION_REGISTRY_UNAVAILABLE",
            "Cannot establish a session right now. Try again shortly.",
            requestId,
          ),
        );
      }
      const csrfToken = generateCsrfToken();
      reply.header("set-cookie", [
        issueSessionCookie({
          token: credential.token,
          ttlSeconds: config.sessionTtlSeconds,
          secure: config.cookieSecure,
        }),
        issueCsrfCookie({
          token: csrfToken,
          ttlSeconds: config.sessionTtlSeconds,
          secure: config.cookieSecure,
        }),
      ]);

      reply.code(200);
      return reply.send({
        ...(payload as BackendLoginResponse),
        user,
      });
    } catch (error) {
      const requestId = readRequestId(request.headers);
      const correlationId = readCorrelationId(request.headers);
      app.log.error(
        buildBffLogPayload("bff_session_login_error", request, 502, {
          request_id: requestId,
          correlation_id: correlationId,
          error_code: "BACKEND_PROXY_ERROR",
          error_type: error instanceof Error ? error.name : "Error",
        }),
      );
      return reply.code(502).send(
        buildErrorEnvelope(
          "BACKEND_PROXY_ERROR",
          "Session login request failed.",
          readRequestId(request.headers),
        ),
      );
    }
  });

  app.get("/session/me", async (request, reply) => {
    const credential = readSessionCredentialFromRequest(config, request.headers);
    const requestId = readRequestId(request.headers);
    if (!credential) {
      return reply.code(401).send({
        ...buildErrorEnvelope("MISSING_SESSION", "Missing or invalid session.", requestId),
      });
    }
    try {
      const freshUser = await fetchFreshSessionUser(
        config,
        credential,
        deps?.fetchFn,
      );
      return reply.send({ user: freshUser });
    } catch (error) {
      // Fail closed when the backend cannot confirm the session. Only explicit
      // authentication rejections invalidate the browser session; throttling,
      // server errors, and transport failures must not clear a still-valid cookie.
      const isAuthRejection =
        error instanceof BackendSessionValidationError &&
        (error.statusCode === 401 || error.statusCode === 403);
      app.log.warn(
        buildBffLogPayload("bff_session_validation_failed", request, isAuthRejection ? 401 : 503, {
          request_id: requestId,
          error_code: isAuthRejection ? "SESSION_REVOKED" : "BACKEND_UNAVAILABLE",
          error_type: error instanceof Error ? error.name : "Error",
        }),
      );
      if (isAuthRejection) {
        // Session was explicitly rejected by the backend: clear cookies so the
        // revoked session disappears from the browser.
        reply.header("set-cookie", [
          clearSessionCookie({ secure: config.cookieSecure }),
          clearCsrfCookie({ secure: config.cookieSecure }),
        ]);
        return reply.code(401).send({
          ...buildErrorEnvelope(
            "SESSION_REVOKED",
            "Session is no longer valid. Please sign in again.",
            requestId,
          ),
        });
      }
      // Backend unreachable (not a rejection): fail closed as well, but keep
      // cookies so the user can resume when the backend returns.
      return reply.code(503).send({
        ...buildErrorEnvelope(
          "BACKEND_UNAVAILABLE",
          "Cannot verify session right now. Try again shortly.",
          requestId,
        ),
      });
    }
  });

  app.post("/session/logout", async (request, reply) => {
    const credential = readSessionCredentialFromRequest(config, request.headers);
    if (credential) {
      try {
        await revokeBackendSession(config, credential.sessionId, deps?.fetchFn);
      } catch {
        const requestId = readRequestId(request.headers);
        app.log.warn(
          buildBffLogPayload("bff_session_revocation_failed", request, 503, {
            request_id: requestId,
            error_code: "SESSION_REGISTRY_UNAVAILABLE",
          }),
        );
        return reply.code(503).send(
          buildErrorEnvelope(
            "SESSION_REGISTRY_UNAVAILABLE",
            "Cannot confirm logout right now. Retry shortly.",
            requestId,
          ),
        );
      }
    }
    reply.header("set-cookie", [
      clearSessionCookie({ secure: config.cookieSecure }),
      clearCsrfCookie({ secure: config.cookieSecure }),
    ]);
    return reply.send({ success: true });
  });

  // The proxy handler is shared by the wildcard route and the dedicated restore route,
  // so it takes the wildcard path as a parameter instead of reading `params["*"]`: a
  // route with no wildcard segment has no such param.
  const handleBackendProxy = async (
    request: FastifyRequest,
    reply: FastifyReply,
    rawWildcardPath: string,
  ) => {
      const backendPath = normalizeBackendPath(rawWildcardPath);
      if (!backendPath) {
        return reply.code(400).send(
          buildErrorEnvelope("INVALID_BACKEND_PATH", "Invalid backend path.", readRequestId(request.headers)),
        );
      }

      if (!isAllowlistedRoute(request.method, backendPath)) {
        return reply.code(403).send(
          buildErrorEnvelope(
            "ROUTE_NOT_ALLOWLISTED",
            "Route not allowlisted by spa-bff policy.",
            readRequestId(request.headers),
          ),
        );
      }
      const operationId = resolveAllowlistedOperation(request.method, backendPath);
      if (!operationId) {
        return reply.code(500).send(
          buildErrorEnvelope("OPENAPI_OPERATION_MISSING", "Allowlisted route lacks an OpenAPI operation mapping.", readRequestId(request.headers)),
        );
      }

      const actorRequired = requiresActorHeader(request.method, backendPath);
      let actor: string | null = null;
      let sessionUser: SessionUser | null = null;
      let sessionCredential: SessionCredential | null = null;
      const isReadRoute = backendPath.startsWith("/v1/read/");
      if (actorRequired) {
        sessionCredential = readSessionCredentialFromRequest(config, request.headers);
        if (!sessionCredential) {
          return reply.code(401).send({
            ...buildErrorEnvelope(
              "MISSING_SESSION",
              "Missing or invalid session for actor-scoped route.",
              readRequestId(request.headers),
            ),
          });
        }
        sessionUser = sessionCredential.user;
        if (!Number.isSafeInteger(sessionUser.token_version) || (sessionUser.token_version ?? 0) <= 0) {
          return reply.code(401).send(buildErrorEnvelope(
            "INVALID_TOKEN_VERSION",
            "Session must be renewed before accessing this operation.",
            readRequestId(request.headers),
          ));
        }
        actor = sessionUser.username;

        // CSRF protection: validate double-submit cookie on state-changing requests.
        // Read routes are intentionally POST-based but non-mutating and do not
        // require CSRF in this API contract.
        const isStateChanging =
          ["POST", "PATCH", "PUT", "DELETE"].includes(request.method) &&
          !isReadRoute;
        if (isStateChanging) {
          const csrfValid = validateCsrfToken({
            cookieHeader: firstHeaderValue(request.headers.cookie),
            headerValue: request.headers["x-xsrf-token"],
          });
          if (!csrfValid) {
            return reply.code(403).send({
              ...buildErrorEnvelope(
                "INVALID_CSRF_TOKEN",
                "CSRF token validation failed. Include X-XSRF-TOKEN header matching the okr_csrf_token cookie.",
                readRequestId(request.headers),
              ),
            });
          }
        }
      }

    if (actorRequired) {
        const attemptedActor = firstHeaderValue(request.headers["x-okr-actor"]);
        if (attemptedActor && actor && attemptedActor !== actor) {
          app.log.warn(
            buildBffLogPayload("bff_actor_header_rewrite", request, 403, {
              attempted_actor: attemptedActor,
              session_actor: actor,
              path: backendPath,
            }),
          );
          return reply.code(403).send({
            ...buildErrorEnvelope(
              "INVALID_ACTOR_HEADER",
              "Client-supplied X-OKR-Actor header does not match the authenticated session actor.",
              readRequestId(request.headers),
            ),
          });
        }
      }

      const queryIndex = request.url.indexOf("?");
      const queryString = queryIndex >= 0 ? request.url.slice(queryIndex) : "";

      try {
        const sessionRoleHeaders: Record<string, string> = {};
        if (sessionUser?.role) {
          sessionRoleHeaders["x-okr-role"] = sessionUser.role;
        }
        if (sessionUser?.roles && sessionUser.roles.length > 0) {
          sessionRoleHeaders["x-okr-roles"] = sessionUser.roles.join(",");
        }

        const result = await proxyToBackend(
          config,
          {
            method: request.method,
            path: backendPath,
            queryString,
            body: request.body,
            actor,
            tokenVersion: sessionUser?.token_version,
            sessionId: sessionCredential?.sessionId,
            sessionActor: sessionCredential ? String(sessionUser?.id) : undefined,
            incomingHeaders: { ...request.headers, ...sessionRoleHeaders },
          },
          deps,
        );

        for (const [headerName, headerValue] of result.headers.entries()) {
          if (RESPONSE_HEADER_BLOCKLIST.has(headerName.toLowerCase())) {
            continue;
          }
          reply.header(headerName, headerValue);
        }
        appendUpstreamServerTiming(reply, result, request.method, request.url);

        reply.code(result.status);
        if (result.body.length === 0) {
          if (result.status >= 400) {
            return reply.send(
              buildBackendErrorEnvelope(result.status, Buffer.alloc(0), readRequestId(request.headers)),
            );
          }
          return reply.send();
        }
        if (result.status >= 400) {
          return reply.send(
            buildBackendErrorEnvelope(result.status, result.body, readRequestId(request.headers)),
          );
        }
        return reply.send(result.body);
    } catch (error) {
      const requestId = readRequestId(request.headers);
      const correlationId = readCorrelationId(request.headers);
      app.log.error(
        buildBffLogPayload("bff_backend_proxy_error", request, 502, {
          request_id: requestId,
          correlation_id: correlationId,
          error_code: "BACKEND_PROXY_ERROR",
          error_type: error instanceof Error ? error.name : "Error",
          path: backendPath,
        }),
      );
      return reply.code(502).send({
        ...buildErrorEnvelope(
          "BACKEND_PROXY_ERROR",
            "Backend proxy request failed.",
            readRequestId(request.headers),
          ),
        });
      }
  };

  app.route<{ Params: WildcardParams }>({
    method: ["GET", "POST", "PATCH", "PUT", "DELETE"],
    url: "/api/backend/*",
    handler: (request, reply) => handleBackendProxy(request, reply, request.params["*"]),
  });

  // The one route that carries a whole backup. A static route wins over the wildcard
  // above, and `bodyLimit` here raises the ceiling for this path only.
  app.route({
    method: "POST",
    url: `/api/backend/${DB_RESTORE_WILDCARD_PATH}`,
    bodyLimit: DB_RESTORE_BODY_LIMIT_BYTES,
    // Fastify buffers the body before the handler runs, so a 50 MiB ceiling would let a
    // caller with no session make this process hold 50 MiB per request. `onRequest` runs
    // before the body is read, so refuse anyone who could not succeed here: no valid
    // signed session, not an admin, or no CSRF pair. These are cheap header and cookie
    // checks. The backend still resolves the admin scope from fresh state, and the
    // handler still runs the full checks; this only decides whether the body is worth
    // reading. A refusal leaves the body unread, and Node discards it without buffering.
    onRequest: async (request, reply) => {
      const requestId = readRequestId(request.headers);
      const credential = readSessionCredentialFromRequest(config, request.headers);
      if (!credential) {
        return reply.code(401).send(
          buildErrorEnvelope("MISSING_SESSION", "Missing or invalid session for actor-scoped route.", requestId),
        );
      }
      if (String(credential.user.role ?? "").trim().toLowerCase() !== "admin") {
        return reply.code(403).send(
          buildErrorEnvelope("ADMIN_REQUIRED", "Admin privileges required.", requestId),
        );
      }
      const csrfValid = validateCsrfToken({
        cookieHeader: firstHeaderValue(request.headers.cookie),
        headerValue: request.headers["x-xsrf-token"],
      });
      if (!csrfValid) {
        return reply.code(403).send(
          buildErrorEnvelope(
            "INVALID_CSRF_TOKEN",
            "CSRF token validation failed. Include X-XSRF-TOKEN header matching the okr_csrf_token cookie.",
            requestId,
          ),
        );
      }
    },
    handler: (request, reply) => handleBackendProxy(request, reply, DB_RESTORE_WILDCARD_PATH),
  });

  return app;
}

async function start(): Promise<void> {
  const config = readConfig(process.env);
  const app = createServer(config);
  let shuttingDown = false;
  const shutdown = async (signal: string): Promise<void> => {
    if (shuttingDown) return;
    shuttingDown = true;
    app.log.info({ signal }, "spa-bff shutting down");
    try {
      await app.close();
      process.exitCode = 0;
    } catch (error) {
      app.log.error({ err: error }, "spa-bff shutdown failure");
      process.exitCode = 1;
    }
  };
  process.once("SIGTERM", () => void shutdown("SIGTERM"));
  process.once("SIGINT", () => void shutdown("SIGINT"));
  try {
    await app.listen({ host: config.host, port: config.port });
    app.log.info({ host: config.host, port: config.port }, "spa-bff started");
  } catch (error) {
    app.log.error({ err: error }, "spa-bff startup failure");
    process.exit(1);
  }
}

const isEntrypoint = process.argv[1]
  ? import.meta.url === pathToFileURL(process.argv[1]).href
  : false;

if (isEntrypoint) {
  void start();
}
