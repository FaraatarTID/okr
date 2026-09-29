import { describe, expect, it, vi } from "vitest";

import type { BffConfig } from "../src/config.js";
import { ALLOWLIST_POLICY_ROUTES } from "../src/allowlist.js";
import { createServer } from "../src/server.js";
import { generateCsrfToken, issueSessionToken, type SessionUser } from "../src/session.js";
import { requestSignatureHex } from "../src/signing.js";

const config: BffConfig = {
  host: "127.0.0.1",
  port: 3001,
  backendApiUrl: "http://backend-api:8100",
  backendServiceToken: "service-token",
  backendSigningSecret: "signing-secret",
  backendSigningKeyId: "key-1",
  requestTimeoutMs: 5_000,
  sessionSecret: "session-secret",
  sessionTtlSeconds: 600,
  cookieSecure: false,
};

const user: SessionUser = {
  id: 19,
  username: "member-19",
  display_name: "Member 19",
  role: "member",
  token_version: 3,
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function payloadFromCookie(cookieHeader: string): Record<string, unknown> {
  const token = decodeURIComponent(/okr_spa_session=([^;]+)/.exec(cookieHeader)?.[1] ?? "");
  const encodedPayload = token.split(".")[0] ?? "";
  return JSON.parse(Buffer.from(encodedPayload, "base64url").toString("utf-8")) as Record<string, unknown>;
}

function mintCookie(sessionUser: SessionUser = user): string {
  const token = issueSessionToken({ user: sessionUser, secret: config.sessionSecret, ttlSeconds: 600 });
  return `okr_spa_session=${encodeURIComponent(token)}; okr_csrf_token=${generateCsrfToken()}`;
}

const actorRequiredRoutes = ALLOWLIST_POLICY_ROUTES.flatMap((rule) =>
  rule.actorRequired
    ? rule.methods.map((method) => ({
        method,
        path: rule.pathTemplate.replace(/\{([^}]+)\}/g, (_match, name: string) =>
          name === "node_type" ? "task" : "1",
        ),
      }))
    : [],
);

function expectedSignature(url: string, options: RequestInit, sessionId?: string, actor?: string): string {
  const headers = options.headers as Record<string, string>;
  const bodyBytes = options.body == null ? null : new TextEncoder().encode(String(options.body));
  return requestSignatureHex({
    method: String(options.method),
    path: new URL(url).pathname,
    timestamp: headers["x-okr-timestamp"],
    nonce: headers["x-okr-nonce"],
    bodyBytes,
    signingSecret: config.backendSigningSecret,
    sessionId,
    sessionActor: actor,
  });
}

describe("BFF shared session registry integration", () => {
  it("registers the fresh session before emitting either cookie", async () => {
    const events: string[] = [];
    const fetchFn = vi.fn().mockImplementation(async (url: string, options: RequestInit) => {
      const path = new URL(url).pathname;
      events.push(path);
      if (path === "/v1/auth/login") {
        return jsonResponse({ success: true, user });
      }
      if (path === "/v1/internal/session-registry/register") {
        expect(events).toEqual([
          "/v1/auth/login",
          "/v1/internal/session-registry/register",
        ]);
        const headers = options.headers as Record<string, string>;
        expect(headers["x-okr-service-token"]).toBe(config.backendServiceToken);
        expect(headers["x-okr-signature"]).toBe(expectedSignature(String(url), options));
        return jsonResponse({ status: "registered" });
      }
      throw new Error(`unexpected backend path ${path}`);
    });
    const app = createServer(config, { fetchFn });
    try {
      const response = await app.inject({
        method: "POST",
        url: "/session/login",
        payload: { username: user.username, password: "secret" },
      });
      expect(response.statusCode).toBe(200);
      expect(events).toHaveLength(2);
      expect(String(response.headers["set-cookie"])).toContain("okr_spa_session=");
      expect(String(response.headers["set-cookie"])).toContain("okr_csrf_token=");
      const [loginUrl, loginOptions] = fetchFn.mock.calls[0] as [string, RequestInit];
      const [, registerOptions] = fetchFn.mock.calls[1] as [string, RequestInit];
      const registered = JSON.parse(String(registerOptions.body)) as Record<string, unknown>;
      const payload = payloadFromCookie(String(response.headers["set-cookie"]));
      expect(registered.session_id).toBe(payload.sid);
      expect(registered.actor_id).toBe(user.id);
      expect(registered.expires_at).toBe(new Date(Number(payload.exp) * 1000).toISOString());
      expect(new URL(loginUrl).pathname).toBe("/v1/auth/login");
      expect(loginOptions.method).toBe("POST");
    } finally {
      await app.close();
    }
  });

  it("returns 503 without setting cookies when registration fails", async () => {
    const fetchFn = vi.fn().mockImplementation(async (url: string) => {
      return new URL(url).pathname === "/v1/auth/login"
        ? jsonResponse({ success: true, user })
        : jsonResponse({ detail: "registry unavailable" }, 503);
    });
    const app = createServer(config, { fetchFn });
    try {
      const response = await app.inject({
        method: "POST",
        url: "/session/login",
        payload: { username: user.username, password: "secret" },
      });
      expect(response.statusCode).toBe(503);
      expect(response.headers["set-cookie"]).toBeUndefined();
    } finally {
      await app.close();
    }
  });

  it("requires the exact registry acknowledgement before login or logout succeeds", async () => {
    const badRegisterAck = vi.fn().mockImplementation(async (url: string) =>
      new URL(url).pathname === "/v1/auth/login"
        ? jsonResponse({ success: true, user })
        : jsonResponse({ status: "revoked" }),
    );
    const loginApp = createServer(config, { fetchFn: badRegisterAck });
    try {
      const response = await loginApp.inject({
        method: "POST",
        url: "/session/login",
        payload: { username: user.username, password: "secret" },
      });
      expect(response.statusCode).toBe(503);
      expect(response.headers["set-cookie"]).toBeUndefined();
    } finally {
      await loginApp.close();
    }

    const cookie = mintCookie();
    const badRevokeAck = vi.fn().mockResolvedValue(jsonResponse({ status: "registered" }));
    const logoutApp = createServer(config, { fetchFn: badRevokeAck });
    try {
      const response = await logoutApp.inject({
        method: "POST",
        url: "/session/logout",
        headers: { cookie },
      });
      expect(response.statusCode).toBe(503);
      expect(response.headers["set-cookie"]).toBeUndefined();
    } finally {
      await logoutApp.close();
    }
  });

  it.each([
    { url: "/session/me", method: "GET" as const, body: undefined },
    {
      url: "/api/backend/v1/read/query",
      method: "POST" as const,
      body: { kind: "cycles.active", params: {} },
    },
  ])("signs session assertions on actor-required request $url", async ({ url, method, body }) => {
    let observed: { url: string; options: RequestInit } | undefined;
    const fetchFn = vi.fn().mockImplementation(async (target: string, options: RequestInit) => {
      observed = { url: target, options };
      return jsonResponse({ ...user, success: true, user });
    });
    const app = createServer(config, { fetchFn });
    const cookie = mintCookie();
    const payload = payloadFromCookie(cookie);
    try {
      const response = await app.inject({
        method,
        url,
        headers: {
          cookie,
          "x-xsrf-token": cookie.split("okr_csrf_token=")[1],
        },
        payload: body,
      });
      expect(response.statusCode).toBe(200);
      expect(observed).toBeDefined();
      const headers = observed?.options.headers as Record<string, string>;
      expect(headers["x-okr-session-id"]).toBe(payload.sid);
      expect(headers["x-okr-session-actor"]).toBe(String(user.id));
      expect(headers["x-okr-signature"]).toBe(
        expectedSignature(
          observed?.url ?? "",
          observed?.options ?? {},
          String(payload.sid),
          String(user.id),
        ),
      );
      expect(headers.cookie).toBeUndefined();
    } finally {
      await app.close();
    }
  });

  it.each(actorRequiredRoutes)("signs both session assertions for allowlisted $method $path", async ({ method, path }) => {
    let observed: { url: string; options: RequestInit } | undefined;
    const fetchFn = vi.fn().mockImplementation(async (target: string, options: RequestInit) => {
      observed = { url: target, options };
      return jsonResponse({ ok: true });
    });
    const app = createServer(config, { fetchFn });
    // The restore route refuses a non-admin session at the edge, before reading its body,
    // so it cannot be reached with the shared member fixture. Every other route keeps it.
    const isRestore = path === "/v1/admin/db-restore";
    const routeUser: SessionUser = isRestore ? { ...user, role: "admin" } : user;
    const cookie = mintCookie(routeUser);
    const payload = payloadFromCookie(cookie);
    try {
      const response = await app.inject({
        method,
        url: `/api/backend${path}`,
        headers: {
          cookie,
          "x-xsrf-token": cookie.split("okr_csrf_token=")[1],
        },
        payload: ["GET", "DELETE"].includes(method) ? undefined : {},
      });
      expect(response.statusCode, `${method} ${path}`).toBe(200);
      expect(observed).toBeDefined();
      const headers = observed?.options.headers as Record<string, string>;
      expect(headers["x-okr-session-id"]).toBe(payload.sid);
      expect(headers["x-okr-session-actor"]).toBe(String(user.id));
      expect(headers["x-okr-signature"]).toBe(
        expectedSignature(
          observed?.url ?? "",
          observed?.options ?? {},
          String(payload.sid),
          String(user.id),
        ),
      );
      expect(headers.cookie).toBeUndefined();
    } finally {
      await app.close();
    }
  });

  it("revokes before clearing cookies and preserves cookies when revocation fails", async () => {
    const cookie = mintCookie();
    let revokeSeen = false;
    const failingFetch = vi.fn().mockImplementation(async (url: string) => {
      expect(new URL(url).pathname).toBe("/v1/internal/session-registry/revoke");
      revokeSeen = true;
      return jsonResponse({ detail: "registry unavailable" }, 503);
    });
    const app = createServer(config, { fetchFn: failingFetch });
    try {
      const response = await app.inject({
        method: "POST",
        url: "/session/logout",
        headers: { cookie },
      });
      expect(revokeSeen).toBe(true);
      expect(response.statusCode).toBe(503);
      expect(response.headers["set-cookie"]).toBeUndefined();
    } finally {
      await app.close();
    }

    const successfulFetch = vi.fn().mockResolvedValue(jsonResponse({ status: "revoked" }));
    const successApp = createServer(config, { fetchFn: successfulFetch });
    try {
      const response = await successApp.inject({
        method: "POST",
        url: "/session/logout",
        headers: { cookie },
      });
      expect(response.statusCode).toBe(200);
      expect(String(response.headers["set-cookie"])).toContain("Max-Age=0");
      const [target, options] = successfulFetch.mock.calls[0] as [string, RequestInit];
      expect(new URL(target).pathname).toBe("/v1/internal/session-registry/revoke");
      expect(JSON.parse(String(options.body)).session_id).toBe(payloadFromCookie(cookie).sid);
      expect((options.headers as Record<string, string>)["x-okr-signature"]).toBe(
        expectedSignature(target, options),
      );
    } finally {
      await successApp.close();
    }
  });
});
