import { describe, expect, it, vi } from "vitest";

import type { BffConfig } from "../src/config.js";
import { createServer } from "../src/server.js";
import { generateCsrfToken, issueSessionToken, type SessionUser } from "../src/session.js";

const config: BffConfig = {
  host: "127.0.0.1",
  port: 3001,
  backendApiUrl: "http://backend-api:8100",
  backendServiceToken: "test-service-token",
  backendSigningSecret: "test-signing-secret",
  backendSigningKeyId: "test-key-id",
  requestTimeoutMs: 1000,
  sessionSecret: "test-session-secret",
  sessionTtlSeconds: 3600,
  cookieSecure: false,
};

const user: SessionUser = {
  id: 1,
  username: "member-1",
  display_name: "Member One",
  role: "member",
  team_id: 11,
  manager_id: null,
  must_change_password: false,
};

function sessionHeaders(): Record<string, string> {
  const csrf = generateCsrfToken();
  const token = issueSessionToken({
    user,
    secret: config.sessionSecret,
    ttlSeconds: config.sessionTtlSeconds,
  });
  return {
    cookie: `okr_spa_session=${encodeURIComponent(token)}; okr_csrf_token=${csrf}`,
    "x-xsrf-token": csrf,
  };
}

describe("independent service failure isolation", () => {
  it("keeps BFF health local when the backend is unavailable", async () => {
    const fetchFn = vi.fn().mockRejectedValue(new Error("backend unavailable"));
    const app = createServer(config, { fetchFn });

    const health = await app.inject({ method: "GET", url: "/healthz" });
    const protectedRequest = await app.inject({
      method: "GET",
      url: "/session/me",
      headers: sessionHeaders(),
    });
    await app.close();

    expect(health.statusCode).toBe(200);
    expect(health.json()).toEqual({ status: "ok", service: "spa-bff" });
    expect(protectedRequest.statusCode).toBe(503);
    expect(protectedRequest.json()).toMatchObject({
      code: "BACKEND_UNAVAILABLE",
      message: "Cannot verify session right now. Try again shortly.",
    });
    expect(fetchFn).toHaveBeenCalledTimes(1);
  });
});
