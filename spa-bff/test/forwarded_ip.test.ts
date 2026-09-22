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

function mockFetch() {
  return vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ status: "ok" }), {
      status: 200,
      headers: { "content-type": "application/json" },
    }),
  );
}

async function outboundHeaders(
  fetchFn: ReturnType<typeof mockFetch>,
  extraHeaders: Record<string, string>,
): Promise<Record<string, string>> {
  const app = createServer(baseConfig, { fetchFn });
  const response = await app.inject({
    method: "POST",
    url: "/api/backend/v1/read/query",
    headers: {
      ...csrfHeaders(),
      cookie: sessionCookie(),
      ...extraHeaders,
    },
    payload: { kind: "node", params: {} },
  });
  await app.close();

  expect(response.statusCode).toBe(200);
  const [, options] = fetchFn.mock.calls[0] as [string, RequestInit];
  return (options.headers ?? {}) as Record<string, string>;
}

describe("client IP forwarding to the backend", () => {
  it("forwards the private client-IP header the edge set", async () => {
    const fetchFn = mockFetch();

    const headers = await outboundHeaders(fetchFn, { "x-okr-client-ip": "10.0.0.1" });

    expect(headers["x-okr-client-ip"]).toBe("10.0.0.1");
  });

  it("omits the private header when the edge did not set it", async () => {
    const fetchFn = mockFetch();

    const headers = await outboundHeaders(fetchFn, {});

    expect(headers["x-okr-client-ip"]).toBeUndefined();
  });

  it("ignores x-forwarded-for and x-real-ip entirely", async () => {
    // The behavioural half of the trust decision, and the reason the old tests in
    // this file were wrong: they asserted that a client-supplied x-forwarded-for was
    // forwarded to the backend. nginx sets that header with
    // $proxy_add_x_forwarded_for, which appends to the client-supplied chain, so
    // forwarding it let the caller choose the backend's rate-limit key. It must now
    // be dropped, even when present.
    const fetchFn = mockFetch();

    const headers = await outboundHeaders(fetchFn, {
      "x-forwarded-for": "10.0.0.1",
      "x-real-ip": "192.168.1.1",
    });

    expect(headers["x-forwarded-for"]).toBeUndefined();
    expect(headers["x-okr-client-ip"]).toBeUndefined();
  });
});
