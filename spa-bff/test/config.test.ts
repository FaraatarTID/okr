import { describe, expect, it } from "vitest";

import { readConfig } from "../src/config.js";

describe("spa-bff config", () => {
  it("loads defaults with explicit session secret", () => {
    const config = readConfig({
      OKR_BACKEND_API_URL: "http://backend-api:8100",
      OKR_BACKEND_SERVICE_TOKEN: "svc-token",
      BFF_SESSION_SECRET: "session-secret",
    });
    expect(config.requestTimeoutMs).toBe(20_000);
    expect(config.sessionTtlSeconds).toBe(28_800);
    expect(config.cookieSecure).toBe(true);
  });

  it("requires session secret in non-development runtime", () => {
    expect(() =>
      readConfig({
        OKR_BACKEND_API_URL: "http://backend-api:8100",
        OKR_BACKEND_SERVICE_TOKEN: "svc-token",
        NODE_ENV: "production",
      }),
    ).toThrow(/BFF_SESSION_SECRET/);
  });

  it("permits missing session secret in development runtime", () => {
    const config = readConfig({
      OKR_BACKEND_API_URL: "http://backend-api:8100",
      OKR_BACKEND_SERVICE_TOKEN: "svc-token",
      NODE_ENV: "development",
    });
    expect(config.sessionSecret).toMatch(/^[0-9a-f]{64}$/);
    expect(config.cookieSecure).toBe(false);
  });
});
