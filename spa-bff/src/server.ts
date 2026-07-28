import Fastify from "fastify";
import { randomUUID } from "node:crypto";
import { pathToFileURL } from "node:url";

import { isAllowlistedRoute, normalizeBackendPath, requiresActorHeader } from "./allowlist.js";
import type { BffConfig } from "./config.js";
import { readConfig } from "./config.js";
import { proxyToBackend } from "./proxy.js";
import {
  clearSessionCookie,
  clearCsrfCookie,
  generateCsrfToken,
  issueCsrfCookie,
  issueSessionCookie,
  issueSessionToken,
  readSessionUserFromCookie,
  validateCsrfToken,
  type SessionUser,
} from "./session.js";

type WildcardParams = { "*": string };

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

function normalizeSessionUser(value: unknown): SessionUser | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const user = value as Record<string, unknown>;
  const id = Number(user.id);
  const username = String(user.username ?? "").trim();
  const displayName = String(user.display_name ?? "").trim();
  const role = String(user.role ?? "").trim();
  if (!Number.isFinite(id) || id <= 0 || !username || !displayName || !role) {
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

function readSessionUserFromRequest(
  config: BffConfig,
  headers: Record<string, string | string[] | undefined>,
): SessionUser | null {
  return readSessionUserFromCookie({
    cookieHeader: firstHeaderValue(headers.cookie),
    secret: config.sessionSecret,
  });
}

async function fetchFreshSessionUser(
  config: BffConfig,
  sessionUser: SessionUser,
  fetchFn: typeof fetch = globalThis.fetch,
): Promise<SessionUser> {
  const headers: Record<string, string> = {
    "x-okr-actor": sessionUser.username,
    "x-okr-service-token": config.backendServiceToken,
  };
  if (sessionUser.token_version != null) {
    headers["x-okr-token-version"] = String(sessionUser.token_version);
  }
  const response = await fetchFn(`${config.backendApiUrl}/v1/auth/me`, {
    method: "GET",
    headers,
    signal: AbortSignal.timeout(Math.min(config.requestTimeoutMs, 5_000)),
  });
  if (!response.ok) {
    throw new Error(`Backend session validation failed: ${response.status}`);
  }
  const data = (await response.json()) as Record<string, unknown>;
  const user = normalizeSessionUser(data);
  if (!user) {
    throw new Error("Backend returned invalid user data.");
  }
  return user;
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
    bodyLimit: 50 * 1024 * 1024, // 50 MB — generous for backup uploads, prevents multi-GB abuse
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
          ? (payload as Record<string, unknown>)
          : {};
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

      const sessionToken = issueSessionToken({
        user,
        secret: config.sessionSecret,
        ttlSeconds: config.sessionTtlSeconds,
      });
      const csrfToken = generateCsrfToken();
      reply.header("set-cookie", [
        issueSessionCookie({
          token: sessionToken,
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
        ...(payload as Record<string, unknown>),
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
    const sessionUser = readSessionUserFromRequest(config, request.headers);
    const requestId = readRequestId(request.headers);
    if (!sessionUser) {
      return reply.code(401).send({
        ...buildErrorEnvelope("MISSING_SESSION", "Missing or invalid session.", requestId),
      });
    }
    try {
      const freshUser = await fetchFreshSessionUser(
        config,
        sessionUser,
        deps?.fetchFn,
      );
      return reply.send({ user: freshUser });
    } catch {
      // Backend unavailable or validation failed — serve cookie data as fallback
      // so the SPA can still render; freshness is enforced on every actor-scoped request.
      return reply.send({ user: sessionUser });
    }
  });

  app.post("/session/logout", async (_request, reply) => {
    reply.header("set-cookie", [
      clearSessionCookie({ secure: config.cookieSecure }),
      clearCsrfCookie({ secure: config.cookieSecure }),
    ]);
    return reply.send({ success: true });
  });

  app.route<{ Params: WildcardParams }>({
    method: ["GET", "POST", "PATCH", "PUT", "DELETE"],
    url: "/api/backend/*",
    handler: async (request, reply) => {
      const rawWildcardPath = request.params["*"];
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

      const actorRequired = requiresActorHeader(request.method, backendPath);
      let actor: string | null = null;
      let sessionUser: SessionUser | null = null;
      if (actorRequired) {
        sessionUser = readSessionUserFromRequest(config, request.headers);
        if (!sessionUser) {
          return reply.code(401).send({
            ...buildErrorEnvelope(
              "MISSING_SESSION",
              "Missing or invalid session for actor-scoped route.",
              readRequestId(request.headers),
            ),
          });
        }
        actor = sessionUser.username;

        // CSRF protection: validate double-submit cookie on state-changing requests
        const isStateChanging = ["POST", "PATCH", "PUT", "DELETE"].includes(request.method);
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
        }
      }

      const queryIndex = request.url.indexOf("?");
      const queryString = queryIndex >= 0 ? request.url.slice(queryIndex) : "";

      try {
        // Forward token_version header for session revocation validation
        const tokenVersionHeader: Record<string, string> = {};
        if (sessionUser?.token_version != null) {
          tokenVersionHeader["x-okr-token-version"] = String(sessionUser.token_version);
        }

        const result = await proxyToBackend(
          config,
          {
            method: request.method,
            path: backendPath,
            queryString,
            body: request.body,
            actor,
            incomingHeaders: { ...request.headers, ...tokenVersionHeader },
          },
          deps,
        );

        for (const [headerName, headerValue] of result.headers.entries()) {
          if (RESPONSE_HEADER_BLOCKLIST.has(headerName.toLowerCase())) {
            continue;
          }
          reply.header(headerName, headerValue);
        }

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
    },
  });

  return app;
}

async function start(): Promise<void> {
  const config = readConfig(process.env);
  const app = createServer(config);
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
