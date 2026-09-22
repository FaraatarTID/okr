import { afterEach, describe, expect, it, vi } from "vitest";

import type { BffConfig } from "../src/config.js";
import { createServer } from "../src/server.js";
import {
  generateCsrfToken,
  issueSessionToken,
  revokeSessionToken,
  type SessionUser,
} from "../src/session.js";

/**
 * Session revocation ON THE REAL REQUEST PATH, driven through the BFF's own server and
 * the actor-required proxy route rather than through the registry helper.
 *
 * The contract: once a session is logged out, that cookie is rejected on EVERY subsequent
 * request for as long as the signed credential could still be accepted - not just on the
 * first one - and a rejected request never reaches the backend.
 *
 * Scope: this covers same-process replay only. The registry is per-process, so restart and
 * cross-instance revocation remain unresolved, and an unknown session id is still reported
 * as active. No live credentials and no application data: the backend is mocked and every
 * session here is minted locally.
 */

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

const OTHER_USER: SessionUser = {
  ...DEFAULT_USER,
  id: 2,
  username: "member-2",
  display_name: "Member Two",
};

// `/v1/auth/login` is the only actor-OPTIONAL allowlisted route (allowlist.ts:63-65), so
// this route requires the actor and therefore reaches readSessionUserFromRequest and the
// session registry on the real path.
const PROTECTED = "/api/backend/v1/read/query";
const CSRF_TOKEN = generateCsrfToken();

// Controlled clock. Fixed absolute seconds so the token's exp arithmetic is exact and the
// suite does not depend on wall time.
const T0 = 1_800_000_000;
const TTL = 60;
const EXPIRY = T0 + TTL;

function at(epochSeconds: number): void {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(epochSeconds * 1000));
}

function mockFetch() {
  // A fresh Response per call: one Response body can only be read once, so reusing it
  // would make the second proxied request fail with a TypeError and report 502
  // BACKEND_PROXY_ERROR, masking whether the session gate accepted or rejected it.
  return vi.fn().mockImplementation(() =>
    Promise.resolve(
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    ),
  );
}

function mint(user: SessionUser = DEFAULT_USER, nowEpochSeconds: number = T0): string {
  return issueSessionToken({
    user,
    secret: baseConfig.sessionSecret,
    nowEpochSeconds,
    ttlSeconds: TTL,
  });
}

function cookieFor(token: string): string {
  return `okr_spa_session=${encodeURIComponent(token)}; okr_csrf_token=${CSRF_TOKEN}`;
}

type App = ReturnType<typeof createServer>;

async function hitProtected(
  app: App,
  cookie: string,
): Promise<{ statusCode: number; body: Record<string, unknown> }> {
  const response = await app.inject({
    method: "POST",
    url: PROTECTED,
    headers: { "x-xsrf-token": CSRF_TOKEN, cookie },
    payload: { kind: "node", params: {} },
  });
  return {
    statusCode: response.statusCode,
    body: response.json() as Record<string, unknown>,
  };
}

async function logOut(app: App, cookie: string) {
  return app.inject({ method: "POST", url: "/session/logout", headers: { cookie } });
}

describe("session revocation on the real request path", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("rejects a logged-out cookie on every replay and never reaches the backend", async () => {
    at(T0 + 10);
    const fetchFn = mockFetch();
    const app = createServer(baseConfig, { fetchFn });
    try {
      const cookie = cookieFor(mint());

      // Genuinely usable first, so a later rejection cannot be blamed on a broken fixture.
      const before = await hitProtected(app, cookie);
      expect(before.statusCode).toBe(200);
      expect(fetchFn).toHaveBeenCalledTimes(1);

      expect((await logOut(app, cookie)).statusCode).toBe(200);

      const callsAfterLogout = fetchFn.mock.calls.length;
      for (let attempt = 1; attempt <= 3; attempt += 1) {
        const replay = await hitProtected(app, cookie);
        // `code` is the BFF error envelope's field (server.ts:71-87). Asserting it is what
        // attributes the rejection to the session rather than to CSRF (403
        // INVALID_CSRF_TOKEN, and a valid token is sent), rate limiting (429), routing
        // (ROUTE_NOT_ALLOWLISTED), or a backend failure (the fetch is mocked to succeed).
        expect(replay.statusCode).toBe(401);
        expect(replay.body["code"]).toBe("MISSING_SESSION");
      }
      // A rejected request must stop at the actor gate, not reach the backend.
      expect(fetchFn.mock.calls.length).toBe(callsAfterLogout);
    } finally {
      await app.close();
    }
  });

  it("leaves an independent valid session working, so the rejection is session-specific", async () => {
    at(T0 + 10);
    const fetchFn = mockFetch();
    const app = createServer(baseConfig, { fetchFn });
    try {
      const loggedOutCookie = cookieFor(mint(DEFAULT_USER));
      const unaffectedCookie = cookieFor(mint(OTHER_USER));

      await hitProtected(app, loggedOutCookie);
      expect((await logOut(app, loggedOutCookie)).statusCode).toBe(200);

      const rejected = await hitProtected(app, loggedOutCookie);
      expect(rejected.statusCode).toBe(401);
      expect(rejected.body["code"]).toBe("MISSING_SESSION");

      // The control: a blanket denial, a broken fixture, or an exhausted limiter would
      // fail here, and only here is that distinguishable from session-specific rejection.
      const unaffected = await hitProtected(app, unaffectedCookie);
      expect(unaffected.statusCode).toBe(200);
    } finally {
      await app.close();
    }
  });

  it("does not reactivate the credential when logout is repeated", async () => {
    at(T0 + 10);
    const app = createServer(baseConfig, { fetchFn: mockFetch() });
    try {
      const token = mint();
      const cookie = cookieFor(token);
      await hitProtected(app, cookie);

      // Logging out twice must not remove the record, which would make the id unknown and
      // therefore active again.
      expect((await logOut(app, cookie)).statusCode).toBe(200);
      expect((await logOut(app, cookie)).statusCode).toBe(200);
      // The record survived both logouts.
      expect(revokeSessionToken(token)).toBe(true);

      const replay = await hitProtected(app, cookie);
      expect(replay.statusCode).toBe(401);
      expect(replay.body["code"]).toBe("MISSING_SESSION");
    } finally {
      await app.close();
    }
  });

  it("retains revocation across the expiry boundary, including the boundary second", async () => {
    const app = createServer(baseConfig, { fetchFn: mockFetch() });
    try {
      const cookie = cookieFor(mint());
      at(T0 + 1);
      expect((await hitProtected(app, cookie)).statusCode).toBe(200);
      expect((await logOut(app, cookie)).statusCode).toBe(200);

      // Immediately before expiry: exp >= now, so the credential is still acceptable and
      // revocation must still apply.
      at(EXPIRY - 1);
      const beforeExpiry = await hitProtected(app, cookie);
      expect(beforeExpiry.statusCode).toBe(401);
      expect(beforeExpiry.body["code"]).toBe("MISSING_SESSION");

      // Exactly at exp: verifySessionToken rejects only when exp < now, so the credential
      // is STILL acceptable in this second. Asked twice, because the earlier
      // delete-on-revoked behaviour rejected the first request and allowed the second.
      at(EXPIRY);
      const firstAtBoundary = await hitProtected(app, cookie);
      const secondAtBoundary = await hitProtected(app, cookie);
      expect(firstAtBoundary.body["code"]).toBe("MISSING_SESSION");
      expect(secondAtBoundary.body["code"]).toBe("MISSING_SESSION");
      expect(secondAtBoundary.statusCode).toBe(401);

      // Immediately after expiry the credential itself is no longer acceptable.
      at(EXPIRY + 1);
      expect((await hitProtected(app, cookie)).statusCode).toBe(401);
    } finally {
      await app.close();
    }
  });

  it("retains the record while the credential is acceptable and releases it only after", async () => {
    const app = createServer(baseConfig, { fetchFn: mockFetch() });
    try {
      const token = mint();
      const cookie = cookieFor(token);
      at(T0 + 1);
      await hitProtected(app, cookie);
      await logOut(app, cookie);

      // Retained well before expiry, which is what makes every replay rejected. Releasing
      // an unexpired record - for a size cap, say - would recreate the defect.
      at(EXPIRY - 1);
      await hitProtected(app, cookie);
      expect(revokeSessionToken(token)).toBe(true);

      // Only once the credential cannot be accepted at all may the record go. The release
      // is driven by the next ISSUANCE, not by a request: a token past exp is rejected by
      // verifySessionToken's own exp check (session.ts:229) before the registry is ever
      // consulted, so the expiry branch there is unreachable from the request path and
      // pruneExpiredSessions is what actually reclaims these records.
      at(EXPIRY + 1);
      await hitProtected(app, cookie);
      expect(revokeSessionToken(token)).toBe(true); // still held: expiry alone is enough to reject
      mint(DEFAULT_USER, EXPIRY + 1); // a later login runs the expiry-only sweep
      expect(revokeSessionToken(token)).toBe(false);
    } finally {
      await app.close();
    }
  });
});
