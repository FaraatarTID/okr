import { describe, expect, it, vi } from "vitest";

import type { BffConfig } from "../src/config.js";
import { createServer } from "../src/server.js";
import {
  issueSessionToken,
  normalizeSessionUser,
  parseCookieHeader,
  verifySessionTokenClaims,
} from "../src/session.js";

// This file previously tested an in-process map keyed by external subject that no
// request path ever read. It now pins the session-user normaliser and that a
// backend-supplied `external_subject` is carried through login unchanged instead of
// being dropped. This is passthrough only: nothing authorizes or revokes on the
// field, and linking on it stays gated on T19 (see the T23 spec).
// Formerly `identity_session_revocation.test.ts`.

const config: BffConfig = {
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

const BASE_USER = {
  id: 42,
  username: "user@example.test",
  display_name: "Example User",
  role: "member",
};

describe("normalizeSessionUser", () => {
  it("preserves external_subject and trims it", () => {
    const user = normalizeSessionUser({ ...BASE_USER, external_subject: "  subject-42 " });
    expect(user?.external_subject).toBe("subject-42");
  });

  it("omits external_subject when absent, null, or blank", () => {
    expect(normalizeSessionUser(BASE_USER)?.external_subject).toBeUndefined();
    expect(normalizeSessionUser({ ...BASE_USER, external_subject: null })?.external_subject).toBeUndefined();
    expect(normalizeSessionUser({ ...BASE_USER, external_subject: "   " })?.external_subject).toBeUndefined();
  });

  it("rejects records missing a required field", () => {
    expect(normalizeSessionUser(null)).toBeNull();
    expect(normalizeSessionUser({ ...BASE_USER, id: 0 })).toBeNull();
    expect(normalizeSessionUser({ ...BASE_USER, username: "" })).toBeNull();
    expect(normalizeSessionUser({ ...BASE_USER, role: "" })).toBeNull();
  });

  it("keeps token_version only when numeric", () => {
    expect(normalizeSessionUser({ ...BASE_USER, token_version: 3 })?.token_version).toBe(3);
    expect(normalizeSessionUser({ ...BASE_USER, token_version: "3" })?.token_version).toBeUndefined();
  });
});

describe("session cookie round trip", () => {
  it("keeps external_subject through issue and verify", () => {
    const token = issueSessionToken({
      user: { ...BASE_USER, external_subject: "subject-42" },
      secret: config.sessionSecret,
      ttlSeconds: 3600,
    });
    const credential = verifySessionTokenClaims({ token, secret: config.sessionSecret });
    expect(credential?.user.external_subject).toBe("subject-42");
  });

  it("carries external_subject from the backend login response into the signed cookie", async () => {
    const fetchFn = vi.fn().mockImplementation(async (url: string) => {
      if (new URL(url).pathname.endsWith("/session-registry/register")) {
        return new Response(JSON.stringify({ status: "registered" }), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      return new Response(
        JSON.stringify({
          success: true,
          user: { ...BASE_USER, token_version: 1, external_subject: "subject-42" },
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    });
    const app = createServer(config, { fetchFn });
    const response = await app.inject({
      method: "POST",
      url: "/session/login",
      payload: { username: BASE_USER.username, password: "irrelevant" },
    });
    await app.close();

    expect(response.statusCode).toBe(200);
    const setCookie = ([] as string[]).concat(response.headers["set-cookie"] as string | string[]);
    const sessionCookie = setCookie.find((entry) => entry.startsWith("okr_spa_session="));
    expect(sessionCookie).toBeDefined();
    const cookies = parseCookieHeader(String(sessionCookie).split(";")[0]);
    const credential = verifySessionTokenClaims({
      token: cookies["okr_spa_session"],
      secret: config.sessionSecret,
    });
    expect(credential?.user.external_subject).toBe("subject-42");
  });
});
