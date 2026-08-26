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
  backendSigningKeyId: "test-key-id",
  requestTimeoutMs: 5_000,
  sessionSecret: "test-session-secret",
  sessionTtlSeconds: 28_800,
  cookieSecure: false,
};

const TEST_CSRF_TOKEN = generateCsrfToken();

function sessionCookie(user: SessionUser): string {
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

describe("Fix 1: token_version propagation", () => {
  it("session with token_version forwards x-okr-token-version header", async () => {
    const fetchFn = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    const userWithVersion: SessionUser = {
      id: 1,
      username: "admin",
      display_name: "Admin",
      role: "admin",
      team_id: 1,
      manager_id: null,
      must_change_password: false,
      token_version: 3,
    };

    const app = createServer(baseConfig, { fetchFn });
    const response = await app.inject({
      method: "POST",
      url: "/api/backend/v1/read/query",
      headers: {
        ...csrfHeaders(),
        cookie: sessionCookie(userWithVersion),
      },
      payload: { kind: "node", params: {} },
    });
    await app.close();

    expect(response.statusCode).toBe(200);
    expect(fetchFn).toHaveBeenCalledTimes(1);

    const [, options] = fetchFn.mock.calls[0] as [string, RequestInit];
    const headers = (options.headers ?? {}) as Record<string, string>;
    expect(headers["x-okr-token-version"]).toBe("3");
  });

  it("session without token_version omits x-okr-token-version header", async () => {
    const fetchFn = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    const userWithoutVersion: SessionUser = {
      id: 2,
      username: "member",
      display_name: "Member",
      role: "member",
      team_id: 1,
      manager_id: null,
      must_change_password: false,
    };

    const app = createServer(baseConfig, { fetchFn });
    const response = await app.inject({
      method: "POST",
      url: "/api/backend/v1/read/query",
      headers: {
        ...csrfHeaders(),
        cookie: sessionCookie(userWithoutVersion),
      },
      payload: { kind: "node", params: {} },
    });
    await app.close();

    expect(response.statusCode).toBe(200);

    const [, options] = fetchFn.mock.calls[0] as [string, RequestInit];
    const headers = (options.headers ?? {}) as Record<string, string>;
    expect(headers["x-okr-token-version"]).toBeUndefined();
  });

  it("login response includes token_version in session user", async () => {
    const fetchFn = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          success: true,
          user: {
            id: 5,
            username: "admin",
            display_name: "Admin",
            role: "admin",
            team_id: 1,
            manager_id: null,
            must_change_password: false,
            token_version: 7,
          },
        }),
        {
          status: 200,
          headers: { "content-type": "application/json" },
        },
      ),
    );

    const app = createServer(baseConfig, { fetchFn });
    const response = await app.inject({
      method: "POST",
      url: "/session/login",
      payload: { username: "admin", password: "secret" },
    });
    await app.close();

    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.user.token_version).toBe(7);
  });

  it("login response handles missing token_version gracefully", async () => {
    const fetchFn = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          success: true,
          user: {
            id: 6,
            username: "legacy",
            display_name: "Legacy",
            role: "member",
            team_id: 1,
            manager_id: null,
            must_change_password: false,
            // No token_version field
          },
        }),
        {
          status: 200,
          headers: { "content-type": "application/json" },
        },
      ),
    );

    const app = createServer(baseConfig, { fetchFn });
    const response = await app.inject({
      method: "POST",
      url: "/session/login",
      payload: { username: "legacy", password: "secret" },
    });
    await app.close();

    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.user.token_version).toBeUndefined();
  });
});
