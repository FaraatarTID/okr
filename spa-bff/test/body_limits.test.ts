import { describe, expect, it, vi } from "vitest";

import type { BffConfig } from "../src/config.js";
import {
  DB_RESTORE_BODY_LIMIT_BYTES,
  DEFAULT_BODY_LIMIT_BYTES,
  createServer,
} from "../src/server.js";
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

const ADMIN: SessionUser = {
  token_version: 1,
  id: 1,
  username: "admin-1",
  display_name: "Admin One",
  role: "admin",
  team_id: null,
  manager_id: null,
  must_change_password: false,
};

const CSRF_TOKEN = generateCsrfToken();

function authHeaders(): Record<string, string> {
  const token = issueSessionToken({
    user: ADMIN,
    secret: baseConfig.sessionSecret,
    ttlSeconds: baseConfig.sessionTtlSeconds,
  });
  return {
    cookie: `okr_spa_session=${encodeURIComponent(token)}; okr_csrf_token=${CSRF_TOKEN}`,
    "x-xsrf-token": CSRF_TOKEN,
    "content-type": "application/json",
  };
}

function mockFetch() {
  return vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ status: "ok" }), {
      status: 200,
      headers: { "content-type": "application/json" },
    }),
  );
}

// A valid JSON object whose serialized size is just over `bytes`.
function jsonOfSize(bytes: number): string {
  return JSON.stringify({ format: "okr-db-backup/v1", filler: "a".repeat(bytes) });
}

async function post(url: string, payload: string) {
  const fetchFn = mockFetch();
  const app = createServer(baseConfig, { fetchFn });
  const response = await app.inject({ method: "POST", url, headers: authHeaders(), payload });
  await app.close();
  return { response, fetchFn };
}

describe("request body limits", () => {
  it("pins the ceilings so a change to either is deliberate", () => {
    expect(DEFAULT_BODY_LIMIT_BYTES).toBe(1024 * 1024);
    expect(DB_RESTORE_BODY_LIMIT_BYTES).toBe(50 * 1024 * 1024);
  });

  it("rejects an oversize body on an ordinary route with 413, before reaching the backend", async () => {
    const { response, fetchFn } = await post(
      "/api/backend/v1/jobs",
      jsonOfSize(DEFAULT_BODY_LIMIT_BYTES + 1),
    );

    expect(response.statusCode).toBe(413);
    expect(response.json().code).toBe("PAYLOAD_TOO_LARGE");
    expect(fetchFn).not.toHaveBeenCalled();
  });

  it("accepts a body just under the default ceiling on an ordinary route", async () => {
    // Positive control for the rejection above: without it, that test would pass just as
    // well if the route rejected every body for an unrelated reason.
    const { response, fetchFn } = await post(
      "/api/backend/v1/jobs",
      jsonOfSize(DEFAULT_BODY_LIMIT_BYTES - 1024),
    );

    expect(response.statusCode).toBe(200);
    expect(fetchFn).toHaveBeenCalledTimes(1);
  });

  it("rejects an oversize body on the login route", async () => {
    // /session/login is registered separately from the wildcard, so it needs its own case
    // rather than being assumed to inherit the default.
    const { response, fetchFn } = await post(
      "/session/login",
      JSON.stringify({ username: "a", password: "b".repeat(DEFAULT_BODY_LIMIT_BYTES) }),
    );

    expect(response.statusCode).toBe(413);
    expect(fetchFn).not.toHaveBeenCalled();
  });

  it("accepts a body above the default ceiling on the restore route", async () => {
    const { response, fetchFn } = await post(
      "/api/backend/v1/admin/db-restore",
      jsonOfSize(DEFAULT_BODY_LIMIT_BYTES * 4),
    );

    expect(response.statusCode).toBe(200);
    expect(fetchFn).toHaveBeenCalledTimes(1);
  });

  it("still rejects a body above the restore ceiling", async () => {
    const { response, fetchFn } = await post(
      "/api/backend/v1/admin/db-restore",
      jsonOfSize(DB_RESTORE_BODY_LIMIT_BYTES + 1),
    );

    expect(response.statusCode).toBe(413);
    expect(fetchFn).not.toHaveBeenCalled();
  });

  it("keeps the restore route under the same session and CSRF gates as the wildcard", async () => {
    // The dedicated route reuses the shared handler. This proves it did not become an
    // unauthenticated side door: no session cookie must still mean 401 and no backend call.
    const fetchFn = mockFetch();
    const app = createServer(baseConfig, { fetchFn });
    const response = await app.inject({
      method: "POST",
      url: "/api/backend/v1/admin/db-restore",
      headers: { "content-type": "application/json" },
      payload: jsonOfSize(1024),
    });
    await app.close();

    expect(response.statusCode).toBe(401);
    expect(fetchFn).not.toHaveBeenCalled();
  });

  describe("restore route refuses before it buffers the body", () => {
    // Fastify reads the body after `onRequest` and before the handler. A refusal in the
    // handler therefore comes too late to save the memory. `preParsing` runs only for
    // requests that survived `onRequest`, so it is a direct probe of "was the body read".
    async function restore(headers: Record<string, string>, bytes: number) {
      const fetchFn = mockFetch();
      const app = createServer(baseConfig, { fetchFn });
      const reachedBodyParsing = vi.fn();
      app.addHook("preParsing", async () => {
        reachedBodyParsing();
      });
      const response = await app.inject({
        method: "POST",
        url: "/api/backend/v1/admin/db-restore",
        headers,
        payload: jsonOfSize(bytes),
      });
      await app.close();
      return { response, fetchFn, reachedBodyParsing };
    }

    it("does not read a large body from a caller with no session", async () => {
      const { response, fetchFn, reachedBodyParsing } = await restore(
        { "content-type": "application/json" },
        DEFAULT_BODY_LIMIT_BYTES * 8,
      );

      expect(response.statusCode).toBe(401);
      expect(response.json().code).toBe("MISSING_SESSION");
      expect(reachedBodyParsing).not.toHaveBeenCalled();
      expect(fetchFn).not.toHaveBeenCalled();
    });

    it("does not read a large body from a session that is not an admin", async () => {
      const token = issueSessionToken({
        user: { ...ADMIN, id: 2, username: "member-1", role: "member" },
        secret: baseConfig.sessionSecret,
        ttlSeconds: baseConfig.sessionTtlSeconds,
      });
      const { response, fetchFn, reachedBodyParsing } = await restore(
        {
          cookie: `okr_spa_session=${encodeURIComponent(token)}; okr_csrf_token=${CSRF_TOKEN}`,
          "x-xsrf-token": CSRF_TOKEN,
          "content-type": "application/json",
        },
        DEFAULT_BODY_LIMIT_BYTES * 8,
      );

      expect(response.statusCode).toBe(403);
      expect(response.json().code).toBe("ADMIN_REQUIRED");
      expect(reachedBodyParsing).not.toHaveBeenCalled();
      expect(fetchFn).not.toHaveBeenCalled();
    });

    it("does not read a large body from an admin whose CSRF pair is missing", async () => {
      const withoutCsrfHeader = authHeaders();
      delete withoutCsrfHeader["x-xsrf-token"];
      const { response, fetchFn, reachedBodyParsing } = await restore(
        withoutCsrfHeader,
        DEFAULT_BODY_LIMIT_BYTES * 8,
      );

      expect(response.statusCode).toBe(403);
      expect(response.json().code).toBe("INVALID_CSRF_TOKEN");
      expect(reachedBodyParsing).not.toHaveBeenCalled();
      expect(fetchFn).not.toHaveBeenCalled();
    });

    it("does read and forward the body for an admin with a valid CSRF pair", async () => {
      // Positive control: without it, the three cases above would pass just as well if
      // the hook stopped every request, or if `preParsing` never fired at all.
      const { response, fetchFn, reachedBodyParsing } = await restore(
        authHeaders(),
        DEFAULT_BODY_LIMIT_BYTES * 8,
      );

      expect(response.statusCode).toBe(200);
      expect(reachedBodyParsing).toHaveBeenCalledTimes(1);
      expect(fetchFn).toHaveBeenCalledTimes(1);
    });
  });

  it("does not turn a malformed JSON body into a 500", async () => {
    const { response } = await post("/api/backend/v1/jobs", "{not json");

    expect(response.statusCode).toBe(400);
  });
});
