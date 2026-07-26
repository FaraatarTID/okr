import Fastify from "fastify";
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

  app.get("/healthz", async () => {
    return {
      status: "ok",
      service: "spa-bff",
    };
  });

  app.post("/session/login", async (request, reply) => {
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
          return reply.send();
        }
        return reply.send(result.body);
      }

      let payload: unknown;
      try {
        payload = JSON.parse(result.body.toString("utf-8"));
      } catch {
        return reply.code(502).send({
          error: "Backend login response could not be parsed.",
        });
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
          success: false,
          error_code: errorCode || "INVALID_CREDENTIALS",
          detail: message,
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
      request.log.error({ err: error }, "BFF session login failure");
      return reply.code(502).send({
        error: "Session login request failed.",
      });
    }
  });

  app.get("/session/me", async (request, reply) => {
    const sessionUser = readSessionUserFromRequest(config, request.headers);
    if (!sessionUser) {
      return reply.code(401).send({
        error: "Missing or invalid session.",
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
        return reply.code(400).send({ error: "Invalid backend path." });
      }

      if (!isAllowlistedRoute(request.method, backendPath)) {
        return reply.code(403).send({ error: "Route not allowlisted by spa-bff policy." });
      }

      const actorRequired = requiresActorHeader(request.method, backendPath);
      let actor: string | null = null;
      let sessionUser: SessionUser | null = null;
      if (actorRequired) {
        sessionUser = readSessionUserFromRequest(config, request.headers);
        if (!sessionUser) {
          return reply.code(401).send({
            error: "Missing or invalid session for actor-scoped route.",
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
              error: "CSRF token validation failed. Include X-XSRF-TOKEN header matching the okr_csrf_token cookie.",
            });
          }
        }
      }

      if (actorRequired) {
        const attemptedActor = firstHeaderValue(request.headers["x-okr-actor"]);
        if (attemptedActor && actor && attemptedActor !== actor) {
          request.log.warn(
            {
              attempted_actor: attemptedActor,
              session_actor: actor,
              method: request.method,
              path: backendPath,
            },
            "Ignoring client supplied actor header; session actor enforced",
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
          return reply.send();
        }
        return reply.send(result.body);
      } catch (error) {
        request.log.error({ err: error }, "BFF backend proxy failure");
        return reply.code(502).send({
          error: "Backend proxy request failed.",
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
