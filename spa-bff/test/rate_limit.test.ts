import { describe, expect, it, vi } from "vitest";

import { DEFAULT_RATE_LIMIT, readConfig, type BffConfig } from "../src/config.js";
import {
  FixedWindowLimiter,
  classifyRateLimitBucket,
  resolveRateLimitKey,
} from "../src/rate-limit.js";
import { createServer } from "../src/server.js";

describe("FixedWindowLimiter", () => {
  function make(max: number, maxKeys = 100) {
    let now = 1_000_000;
    const limiter = new FixedWindowLimiter({ max, windowMs: 60_000 }, maxKeys, () => now);
    return { limiter, advance: (ms: number) => (now += ms) };
  }

  it("allows up to max requests and refuses the next", () => {
    const { limiter } = make(3);

    expect([1, 2, 3].map(() => limiter.consume("a").allowed)).toEqual([true, true, true]);
    expect(limiter.consume("a").allowed).toBe(false);
  });

  it("reports a whole-second Retry-After of at least one", () => {
    const { limiter, advance } = make(1);
    limiter.consume("a");
    advance(59_500);

    const decision = limiter.consume("a");

    expect(decision.allowed).toBe(false);
    expect(decision.retryAfterSeconds).toBe(1);
  });

  it("counts each key independently", () => {
    const { limiter } = make(1);
    limiter.consume("a");

    expect(limiter.consume("a").allowed).toBe(false);
    expect(limiter.consume("b").allowed).toBe(true);
  });

  it("starts a fresh window once the old one expires", () => {
    const { limiter, advance } = make(1);
    limiter.consume("a");
    expect(limiter.consume("a").allowed).toBe(false);

    advance(60_000);

    expect(limiter.consume("a").allowed).toBe(true);
  });

  it("never tracks more than maxKeys keys", () => {
    const { limiter } = make(5, 10);

    for (let i = 0; i < 1_000; i += 1) {
      limiter.consume(`ip-${i}`);
    }

    expect(limiter.size).toBeLessThanOrEqual(10);
  });

  it("drops expired windows before evicting a live one", () => {
    const { limiter, advance } = make(1, 3);
    limiter.consume("old-1");
    limiter.consume("old-2");
    advance(60_000);
    limiter.consume("live");
    limiter.consume("live"); // now refused: proves "live" holds a counted window

    limiter.consume("new-1");
    limiter.consume("new-2");

    // Room was made from the two expired keys, so the live, over-limit key survived
    // and is still refused rather than having been reset by eviction.
    expect(limiter.consume("live").allowed).toBe(false);
  });

  it("evicts the oldest key when every window is still live", () => {
    const { limiter } = make(1, 2);
    limiter.consume("first");
    limiter.consume("second");

    limiter.consume("third");

    expect(limiter.size).toBe(2);
    // "first" was evicted, so it starts over instead of being refused. This is the
    // documented cost of a hard memory cap.
    expect(limiter.consume("first").allowed).toBe(true);
  });
});

describe("resolveRateLimitKey", () => {
  it("uses the trusted client-ip header when it is a valid address", () => {
    expect(resolveRateLimitKey("203.0.113.9", "10.0.0.2")).toBe("203.0.113.9");
    expect(resolveRateLimitKey("2001:DB8::1", "10.0.0.2")).toBe("2001:db8::1");
  });

  it("falls back to the socket peer when the header is absent", () => {
    // Rule 6 of docs/client-ip-trust-adr.md: a throughput limiter degrades to the peer
    // instead of dropping the key.
    expect(resolveRateLimitKey(undefined, "10.0.0.2")).toBe("10.0.0.2");
    expect(resolveRateLimitKey("", "10.0.0.2")).toBe("10.0.0.2");
  });

  it("ignores a header that is not an IP address, so it cannot inflate the key space", () => {
    expect(resolveRateLimitKey("not-an-ip", "10.0.0.2")).toBe("10.0.0.2");
    expect(resolveRateLimitKey("1.2.3.4, 5.6.7.8", "10.0.0.2")).toBe("10.0.0.2");
    expect(resolveRateLimitKey("a".repeat(500), "10.0.0.2")).toBe("10.0.0.2");
  });

  it("still returns a bounded key with no header and no peer", () => {
    expect(resolveRateLimitKey(undefined, undefined)).toBe("unknown");
  });
});

describe("classifyRateLimitBucket", () => {
  it("puts both login entry points in the login bucket", () => {
    expect(classifyRateLimitBucket("POST", "/session/login")).toBe("login");
    // The catch-all route reaches the same backend login; it must not be a bypass.
    expect(classifyRateLimitBucket("POST", "/api/backend/v1/auth/login")).toBe("login");
  });

  it("is insensitive to a trailing slash, query string and case", () => {
    expect(classifyRateLimitBucket("POST", "/session/login/")).toBe("login");
    expect(classifyRateLimitBucket("POST", "/session/login?x=1")).toBe("login");
    expect(classifyRateLimitBucket("post", "/Session/Login")).toBe("login");
  });

  it("limits the other session routes in the session bucket", () => {
    expect(classifyRateLimitBucket("GET", "/session/me")).toBe("session");
    expect(classifyRateLimitBucket("POST", "/session/logout")).toBe("session");
  });

  it("leaves authenticated backend traffic and health checks unlimited here", () => {
    expect(classifyRateLimitBucket("POST", "/api/backend/v1/read/query")).toBeNull();
    expect(classifyRateLimitBucket("GET", "/healthz")).toBeNull();
    expect(classifyRateLimitBucket("GET", "/session/login")).toBeNull();
  });
});

describe("readConfig rate-limit settings", () => {
  const baseEnv = {
    OKR_BACKEND_API_URL: "http://127.0.0.1:8100",
    OKR_BACKEND_SERVICE_TOKEN: "test-token",
    BFF_SESSION_SECRET: "a-long-enough-development-session-secret",
    NODE_ENV: "development",
  } as NodeJS.ProcessEnv;

  it("defaults to the documented ceilings", () => {
    expect(readConfig(baseEnv).rateLimit).toEqual(DEFAULT_RATE_LIMIT);
  });

  it("reads overrides", () => {
    const config = readConfig({ ...baseEnv, BFF_RATE_LIMIT_LOGIN_MAX: "5" });

    expect(config.rateLimit?.loginMax).toBe(5);
  });

  it("rejects a non-positive value instead of silently disabling the limiter", () => {
    expect(() => readConfig({ ...baseEnv, BFF_RATE_LIMIT_LOGIN_MAX: "0" })).toThrow(
      /BFF_RATE_LIMIT_LOGIN_MAX/,
    );
  });
});

describe("rate limiting on the server", () => {
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
    rateLimit: { windowSeconds: 60, loginMax: 3, sessionMax: 2, maxKeys: 50 },
  };

  function mockFetch() {
    // A fresh Response per call: a body can be read once, so reusing one object would
    // turn every call after the first into a proxy error and hide what is under test.
    return vi.fn().mockImplementation(
      async () =>
        new Response(JSON.stringify({ detail: "Invalid credentials" }), {
          status: 401,
          headers: { "content-type": "application/json" },
        }),
    );
  }

  async function login(
    app: ReturnType<typeof createServer>,
    headers: Record<string, string> = {},
    url = "/session/login",
  ) {
    return app.inject({
      method: "POST",
      url,
      headers,
      payload: { username: "u", password: "password-1" },
    });
  }

  it("answers 429 with Retry-After once the login ceiling is passed, before the backend", async () => {
    const fetchFn = mockFetch();
    const app = createServer(config, { fetchFn });

    const statuses: number[] = [];
    for (let i = 0; i < 4; i += 1) {
      statuses.push((await login(app, { "x-okr-client-ip": "203.0.113.9" })).statusCode);
    }
    const blocked = await login(app, { "x-okr-client-ip": "203.0.113.9" });
    await app.close();

    expect(statuses).toEqual([401, 401, 401, 429]);
    expect(blocked.statusCode).toBe(429);
    expect(blocked.json().code).toBe("RATE_LIMITED");
    expect(Number(blocked.headers["retry-after"])).toBeGreaterThanOrEqual(1);
    // Exactly the three allowed attempts reached the backend; the refused ones did not.
    expect(fetchFn).toHaveBeenCalledTimes(3);
  });

  it("limits per client, so one address cannot exhaust another's allowance", async () => {
    const app = createServer(config, { fetchFn: mockFetch() });
    for (let i = 0; i < 4; i += 1) {
      await login(app, { "x-okr-client-ip": "203.0.113.9" });
    }

    const other = await login(app, { "x-okr-client-ip": "198.51.100.4" });
    await app.close();

    expect(other.statusCode).toBe(401);
  });

  it("does not let X-Forwarded-For choose the key", async () => {
    // The whole point of ignoring `request.ip`: rotating a spoofed X-Forwarded-For must
    // not mint a fresh allowance per request.
    const app = createServer(config, { fetchFn: mockFetch() });

    const statuses: number[] = [];
    for (let i = 0; i < 5; i += 1) {
      statuses.push(
        (await login(app, { "x-forwarded-for": `192.0.2.${i + 1}` })).statusCode,
      );
    }
    await app.close();

    expect(statuses).toEqual([401, 401, 401, 429, 429]);
  });

  it("applies the same login bucket to the catch-all login route", async () => {
    const app = createServer(config, { fetchFn: mockFetch() });
    const headers = { "x-okr-client-ip": "203.0.113.9" };
    for (let i = 0; i < 3; i += 1) {
      await login(app, headers, "/session/login");
    }

    const viaCatchAll = await login(app, headers, "/api/backend/v1/auth/login");
    await app.close();

    expect(viaCatchAll.statusCode).toBe(429);
  });

  it("limits /session/me in its own, looser bucket", async () => {
    const app = createServer(config, { fetchFn: mockFetch() });
    const headers = { "x-okr-client-ip": "203.0.113.9" };
    for (let i = 0; i < 4; i += 1) {
      await login(app, headers);
    }

    // Login is exhausted for this address, but `me` has its own budget of 2.
    const me = await app.inject({ method: "GET", url: "/session/me", headers });
    const me2 = await app.inject({ method: "GET", url: "/session/me", headers });
    const me3 = await app.inject({ method: "GET", url: "/session/me", headers });
    await app.close();

    expect(me.statusCode).not.toBe(429);
    expect(me2.statusCode).not.toBe(429);
    expect(me3.statusCode).toBe(429);
  });

  it("never limits the health check", async () => {
    const app = createServer(config, { fetchFn: mockFetch() });

    const statuses: number[] = [];
    for (let i = 0; i < 20; i += 1) {
      statuses.push((await app.inject({ method: "GET", url: "/healthz" })).statusCode);
    }
    await app.close();

    expect(new Set(statuses)).toEqual(new Set([200]));
  });

  it("uses the default ceilings when the config carries none", async () => {
    const withoutRateLimit: BffConfig = { ...config };
    delete withoutRateLimit.rateLimit;
    const app = createServer(withoutRateLimit, { fetchFn: mockFetch() });

    const first = await login(app, { "x-okr-client-ip": "203.0.113.9" });
    await app.close();

    expect(first.statusCode).toBe(401);
  });
});
