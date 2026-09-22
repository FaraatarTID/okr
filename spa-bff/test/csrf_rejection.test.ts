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

// The CSRF double-submit pair: the token is both in the cookie and, on a valid
// request, in the X-XSRF-TOKEN header. Tests vary only the header half.
const CSRF_TOKEN = generateCsrfToken();

function sessionCookie(): string {
  const token = issueSessionToken({
    user: DEFAULT_USER,
    secret: baseConfig.sessionSecret,
    ttlSeconds: baseConfig.sessionTtlSeconds,
  });
  return `okr_spa_session=${encodeURIComponent(token)}; okr_csrf_token=${CSRF_TOKEN}`;
}

function mockFetch() {
  return vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ status: "ok" }), {
      status: 200,
      headers: { "content-type": "application/json" },
    }),
  );
}

async function post(
  fetchFn: ReturnType<typeof mockFetch>,
  url: string,
  headers: Record<string, string>,
) {
  const app = createServer(baseConfig, { fetchFn });
  const response = await app.inject({
    method: "POST",
    url,
    headers: { cookie: sessionCookie(), ...headers },
    payload: {},
  });
  await app.close();
  return response;
}

// A state-changing backend route (not /v1/read/*, which the contract exempts).
const STATE_CHANGING = "/api/backend/v1/jobs";

describe("CSRF rejection on state-changing routes", () => {
  it("rejects a request with no X-XSRF-TOKEN header", async () => {
    // The branch this file exists for. Every other test in this suite supplies a valid
    // token, so this rejection path had no coverage at all.
    const fetchFn = mockFetch();

    const response = await post(fetchFn, STATE_CHANGING, {});

    expect(response.statusCode).toBe(403);
    expect(response.body).toContain("INVALID_CSRF_TOKEN");
    expect(fetchFn).not.toHaveBeenCalled();
  });

  it("rejects a header that does not match the cookie", async () => {
    const fetchFn = mockFetch();

    const response = await post(fetchFn, STATE_CHANGING, {
      "x-xsrf-token": generateCsrfToken(),
    });

    expect(response.statusCode).toBe(403);
    expect(response.body).toContain("INVALID_CSRF_TOKEN");
    expect(fetchFn).not.toHaveBeenCalled();
  });

  it("allows the request when the header matches the cookie", async () => {
    // Positive control. Without it, the two tests above would pass just as well if the
    // route were rejecting everything for an unrelated reason - a missing session, a
    // routing miss, or a path that never reaches this branch.
    const fetchFn = mockFetch();

    const response = await post(fetchFn, STATE_CHANGING, { "x-xsrf-token": CSRF_TOKEN });

    expect(response.body).not.toContain("INVALID_CSRF_TOKEN");
    expect(response.statusCode).toBe(200);
    expect(fetchFn).toHaveBeenCalled();
  });

  it("exempts read routes, which are POST-based but non-mutating", async () => {
    // Documents that the exemption is deliberate rather than an accident of which
    // methods happen to reach the check.
    const fetchFn = mockFetch();

    const response = await post(fetchFn, "/api/backend/v1/read/query", {});

    expect(response.body).not.toContain("INVALID_CSRF_TOKEN");
    expect(fetchFn).toHaveBeenCalled();
  });
});
