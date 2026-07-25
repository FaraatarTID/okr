import { describe, expect, it, vi } from "vitest";

import type { BffConfig } from "../src/config.js";
import { createServer } from "../src/server.js";
import { generateCsrfToken, issueSessionToken, type SessionUser } from "../src/session.js";

const baseConfig: BffConfig = {
  host: "127.0.0.1",
  port: 3001,
  backendApiUrl: "http://backend-api:8100",
  backendServiceToken: "test-token",
  backendSigningSecret: "test-signing-secret",
  requestTimeoutMs: 5_000,
  sessionSecret: "test-session-secret",
  sessionTtlSeconds: 28_800,
  cookieSecure: false,
};

const DEFAULT_USER: SessionUser = {
  id: 1,
  username: "member-1",
  display_name: "Member One",
  role: "member",
  team_id: 11,
  manager_id: null,
  must_change_password: false,
};

const TEST_CSRF_TOKEN = generateCsrfToken();

function sessionCookie(user: SessionUser = DEFAULT_USER): string {
  const token = issueSessionToken({
    user,
    secret: baseConfig.sessionSecret,
    ttlSeconds: baseConfig.sessionTtlSeconds,
  });
  return `okr_spa_session=${encodeURIComponent(token)}; okr_csrf_token=${TEST_CSRF_TOKEN}`;
}

function csrfHeaders(): Record<string, string> {
  return { "x-xsrf-token": TEST_CSRF_TOKEN };
}

describe("Fix 2: x-forwarded-for proxy forwarding", () => {
  it("forwards x-forwarded-for from client to backend", async () => {
    const fetchFn = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    const app = createServer(baseConfig, { fetchFn });
    const response = await app.inject({
      method: "POST",
      url: "/api/backend/v1/read/query",
      headers: {
        ...csrfHeaders(),
        cookie: sessionCookie(),
        "x-forwarded-for": "10.0.0.1",
      },
      payload: { kind: "node", params: {} },
    });
    await app.close();

    expect(response.statusCode).toBe(200);

    const [, options] = fetchFn.mock.calls[0] as [string, RequestInit];
    const headers = (options.headers ?? {}) as Record<string, string>;
    expect(headers["x-forwarded-for"]).toBe("10.0.0.1");
  });

  it("omits x-forwarded-for when not present in client request", async () => {
    const fetchFn = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    const app = createServer(baseConfig, { fetchFn });
    const response = await app.inject({
      method: "POST",
      url: "/api/backend/v1/read/query",
      headers: {
        ...csrfHeaders(),
        cookie: sessionCookie(),
      },
      payload: { kind: "node", params: {} },
    });
    await app.close();

    expect(response.statusCode).toBe(200);

    const [, options] = fetchFn.mock.calls[0] as [string, RequestInit];
    const headers = (options.headers ?? {}) as Record<string, string>;
    expect(headers["x-forwarded-for"]).toBeUndefined();
  });

  it("prefers x-forwarded-for over x-real-ip", async () => {
    const fetchFn = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    const app = createServer(baseConfig, { fetchFn });
    const response = await app.inject({
      method: "POST",
      url: "/api/backend/v1/read/query",
      headers: {
        ...csrfHeaders(),
        cookie: sessionCookie(),
        "x-forwarded-for": "10.0.0.1",
        "x-real-ip": "192.168.1.1",
      },
      payload: { kind: "node", params: {} },
    });
    await app.close();

    const [, options] = fetchFn.mock.calls[0] as [string, RequestInit];
    const headers = (options.headers ?? {}) as Record<string, string>;
    expect(headers["x-forwarded-for"]).toBe("10.0.0.1");
  });
});
