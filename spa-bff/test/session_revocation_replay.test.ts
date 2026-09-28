import { afterEach, describe, expect, it, vi } from "vitest";

import type { BffConfig } from "../src/config.js";
import { createServer } from "../src/server.js";
import { generateCsrfToken, issueSessionToken, type SessionUser } from "../src/session.js";

const config: BffConfig = {
  host: "127.0.0.1",
  port: 3001,
  backendApiUrl: "http://backend-api:8100",
  backendServiceToken: "test-token",
  backendSigningSecret: "test-signing-secret",
  backendSigningKeyId: "test-key-id",
  requestTimeoutMs: 5_000,
  sessionSecret: "test-session-secret",
  sessionTtlSeconds: 60,
  cookieSecure: false,
};

const user: SessionUser = {
  token_version: 1,
  id: 1,
  username: "member-1",
  display_name: "Member One",
  role: "member",
};

const T0 = 1_800_000_000;
const TTL = 60;
const EXPIRY = T0 + TTL;
const CSRF = generateCsrfToken();
const protectedPath = "/v1/read/query";

function at(epochSeconds: number): void {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(epochSeconds * 1000));
}

function mint(nowEpochSeconds = T0): { token: string; sessionId: string; cookie: string } {
  const token = issueSessionToken({
    user,
    secret: config.sessionSecret,
    nowEpochSeconds,
    ttlSeconds: TTL,
  });
  const payload = JSON.parse(Buffer.from(token.split(".")[0] ?? "", "base64url").toString("utf-8")) as {
    sid: string;
  };
  return {
    token,
    sessionId: payload.sid,
    cookie: `okr_spa_session=${encodeURIComponent(token)}; okr_csrf_token=${CSRF}`,
  };
}

function registryBackend() {
  const sessions = new Map<string, { actorId: number; expiresAt: number; revoked: boolean }>();
  let unavailable = false;
  let protectedWork = 0;
  const fetchFn = vi.fn().mockImplementation(async (url: string, options: RequestInit) => {
    const path = new URL(url).pathname;
    if (unavailable) {
      return new Response(JSON.stringify({ detail: "registry unavailable" }), {
        status: 503,
        headers: { "content-type": "application/json" },
      });
    }
    if (path.endsWith("/session-registry/register")) {
      const body = JSON.parse(String(options.body)) as {
        session_id: string;
        actor_id: number;
        expires_at: string;
      };
      sessions.set(body.session_id, {
        actorId: body.actor_id,
        expiresAt: Math.floor(Date.parse(body.expires_at) / 1000),
        revoked: false,
      });
      return new Response(JSON.stringify({ status: "registered" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    if (path.endsWith("/session-registry/revoke")) {
      const body = JSON.parse(String(options.body)) as { session_id: string };
      const record = sessions.get(body.session_id);
      if (record) record.revoked = true;
      return new Response(JSON.stringify({ status: "revoked" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    if (path === "/v1/auth/me" || path === protectedPath) {
      const headers = options.headers as Record<string, string>;
      const sid = headers["x-okr-session-id"];
      const actorId = Number(headers["x-okr-session-actor"]);
      const record = sessions.get(sid);
      if (!record || record.revoked || record.actorId !== actorId || record.expiresAt < Math.floor(Date.now() / 1000)) {
        return new Response(JSON.stringify({ detail: "Session is not active." }), {
          status: 401,
          headers: { "content-type": "application/json" },
        });
      }
      protectedWork += 1;
      return new Response(JSON.stringify({ success: true, user }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    return new Response(JSON.stringify({ status: "ok" }), { status: 200 });
  });
  return {
    fetchFn,
    sessions,
    setUnavailable(value: boolean) { unavailable = value; },
    get protectedWork() { return protectedWork; },
  };
}

async function protectedRequest(app: ReturnType<typeof createServer>, cookie: string) {
  return app.inject({
    method: "POST",
    url: "/api/backend/v1/read/query",
    headers: { cookie, "x-xsrf-token": CSRF },
    payload: { kind: "cycles.active", params: {} },
  });
}

describe("session revocation through the backend authority", () => {
  afterEach(() => vi.useRealTimers());

  it("revokes only one of two sessions for the same actor", async () => {
    at(T0 + 10);
    const backend = registryBackend();
    const app = createServer(config, { fetchFn: backend.fetchFn });
    const first = mint();
    const second = mint();
    backend.sessions.set(first.sessionId, { actorId: user.id, expiresAt: EXPIRY, revoked: false });
    backend.sessions.set(second.sessionId, { actorId: user.id, expiresAt: EXPIRY, revoked: false });
    try {
      expect((await protectedRequest(app, first.cookie)).statusCode).toBe(200);
      expect((await protectedRequest(app, second.cookie)).statusCode).toBe(200);
      const logout = await app.inject({
        method: "POST",
        url: "/session/logout",
        headers: { cookie: first.cookie },
      });
      expect(logout.statusCode).toBe(200);

      const rejected = await protectedRequest(app, first.cookie);
      expect(rejected.statusCode).toBe(401);
      expect(rejected.json().code).toBe("HTTP_401");
      expect((await protectedRequest(app, second.cookie)).statusCode).toBe(200);
      expect(backend.protectedWork).toBe(3);
      expect(backend.sessions.get(first.sessionId)?.revoked).toBe(true);
      expect(backend.sessions.get(second.sessionId)?.revoked).toBe(false);
    } finally {
      await app.close();
    }
  });

  it("forwards an unknown signed cookie to the backend, which rejects before protected work", async () => {
    at(T0 + 1);
    const backend = registryBackend();
    const app = createServer(config, { fetchFn: backend.fetchFn });
    const unknown = mint();
    try {
      const response = await protectedRequest(app, unknown.cookie);
      expect(response.statusCode).toBe(401);
      expect(response.json().code).toBe("HTTP_401");
      expect(backend.protectedWork).toBe(0);
    } finally {
      await app.close();
    }
  });

  it("retains rejected logout credentials on provider outage and rejects provider outage on protected calls", async () => {
    at(T0 + 1);
    const backend = registryBackend();
    const app = createServer(config, { fetchFn: backend.fetchFn });
    const registered = mint();
    backend.sessions.set(registered.sessionId, { actorId: user.id, expiresAt: EXPIRY, revoked: false });
    try {
      backend.setUnavailable(true);
      const logout = await app.inject({
        method: "POST",
        url: "/session/logout",
        headers: { cookie: registered.cookie },
      });
      expect(logout.statusCode).toBe(503);
      expect(logout.headers["set-cookie"]).toBeUndefined();

      const protectedResponse = await protectedRequest(app, registered.cookie);
      expect(protectedResponse.statusCode).toBe(503);
      expect(backend.protectedWork).toBe(0);
    } finally {
      await app.close();
    }
  });

  it("preserves revocation through the accepted expiry second", async () => {
    const backend = registryBackend();
    const app = createServer(config, { fetchFn: backend.fetchFn });
    const registered = mint();
    backend.sessions.set(registered.sessionId, { actorId: user.id, expiresAt: EXPIRY, revoked: true });
    try {
      at(EXPIRY);
      const atBoundary = await protectedRequest(app, registered.cookie);
      expect(atBoundary.statusCode).toBe(401);
      expect(backend.protectedWork).toBe(0);

      at(EXPIRY + 1);
      const afterExpiry = await protectedRequest(app, registered.cookie);
      expect(afterExpiry.statusCode).toBe(401);
      expect(backend.fetchFn).toHaveBeenCalledTimes(1);
    } finally {
      await app.close();
    }
  });
});
