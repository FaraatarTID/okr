import { describe, expect, it } from "vitest";

import { readConfig } from "../src/config.js";

describe("spa-bff config", () => {
  it("loads defaults with explicit session secret", () => {
    const config = readConfig({
      OKR_BACKEND_API_URL: "http://backend-api:8100",
      OKR_BACKEND_SERVICE_TOKEN: "svc-token",
      BFF_SESSION_SECRET: "a-very-secure-session-secret-that-is-at-least-32-chars",
    });
    expect(config.requestTimeoutMs).toBe(20_000);
    expect(config.sessionTtlSeconds).toBe(28_800);
    expect(config.cookieSecure).toBe(true);
  });

  it("rejects insecure default session secrets", () => {
    expect(() =>
      readConfig({
        OKR_BACKEND_API_URL: "http://backend-api:8100",
        OKR_BACKEND_SERVICE_TOKEN: "svc-token",
        BFF_SESSION_SECRET: "change-me",
      }),
    ).toThrow(/insecure default/);
  });

  it("rejects short session secrets", () => {
    expect(() =>
      readConfig({
        OKR_BACKEND_API_URL: "http://backend-api:8100",
        OKR_BACKEND_SERVICE_TOKEN: "svc-token",
        BFF_SESSION_SECRET: "short",
      }),
    ).toThrow(/at least 32 characters/);
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

  it("requires backend signing secret in production", () => {
    expect(() =>
      readConfig({
        OKR_BACKEND_API_URL: "http://backend-api:8100",
        OKR_BACKEND_SERVICE_TOKEN: "svc-token",
        BFF_SESSION_SECRET: "a-very-secure-session-secret-that-is-at-least-32-chars",
        NODE_ENV: "production",
      }),
    ).toThrow(/OKR_BACKEND_(SERVICE_TOKEN|SIGNING_SECRET)/);
  });

  it("rejects placeholder backend service token and signing secret in production", () => {
    expect(() =>
      readConfig({
        OKR_BACKEND_API_URL: "http://backend-api:8100",
        OKR_BACKEND_SERVICE_TOKEN: "CHANGE_ME_SHARED_TOKEN",
        OKR_BACKEND_SIGNING_SECRET: "CHANGE_ME_SIGNING_SECRET",
        BFF_SESSION_SECRET: "a-very-secure-session-secret-that-is-at-least-32-chars",
        NODE_ENV: "production",
      }),
    ).toThrow(/strong non-placeholder value/);
  });

  it("accepts production config with strong service/signing secrets", () => {
    const config = readConfig({
      OKR_BACKEND_API_URL: "http://backend-api:8100",
      OKR_BACKEND_SERVICE_TOKEN: "svc-token-with-more-than-24-chars",
      OKR_BACKEND_SIGNING_SECRET: "signing-secret-that-is-longer-than-thirty-two",
      BFF_SESSION_SECRET: "a-very-secure-session-secret-that-is-at-least-32-chars",
      NODE_ENV: "production",
    });
    expect(config.backendServiceToken).toBe("svc-token-with-more-than-24-chars");
    expect(config.backendSigningSecret).toBe("signing-secret-that-is-longer-than-thirty-two");
  });

  it("uses OKR_ENV as a production signal", () => {
    const config = readConfig({
      OKR_BACKEND_API_URL: "http://backend-api:8100",
      OKR_ENV: "production",
      OKR_BACKEND_SERVICE_TOKEN: "svc-token-with-more-than-24-chars",
      OKR_BACKEND_SIGNING_SECRET: "signing-secret-that-is-longer-than-thirty-two",
      BFF_SESSION_SECRET: "a-very-secure-session-secret-that-is-at-least-32-chars",
      BFF_COOKIE_SECURE: "true",
    });
    expect(config.cookieSecure).toBe(true);
    expect(config.backendServiceToken).toBe("svc-token-with-more-than-24-chars");
    expect(config.backendSigningSecret).toBe("signing-secret-that-is-longer-than-thirty-two");
  });

  it("requires secure cookies in production", () => {
    expect(() =>
      readConfig({
        OKR_BACKEND_API_URL: "http://backend-api:8100",
        OKR_BACKEND_SERVICE_TOKEN: "svc-token-with-more-than-24-chars",
        OKR_BACKEND_SIGNING_SECRET: "signing-secret-that-is-longer-than-thirty-two",
        BFF_SESSION_SECRET: "a-very-secure-session-secret-that-is-at-least-32-chars",
        BFF_COOKIE_SECURE: "false",
        NODE_ENV: "production",
      }),
    ).toThrow(/BFF_COOKIE_SECURE/);
  });

  it("accepts secure cookies in production", () => {
    const config = readConfig({
      OKR_BACKEND_API_URL: "http://backend-api:8100",
      OKR_BACKEND_SERVICE_TOKEN: "svc-token-with-more-than-24-chars",
      OKR_BACKEND_SIGNING_SECRET: "signing-secret-that-is-longer-than-thirty-two",
      BFF_SESSION_SECRET: "a-very-secure-session-secret-that-is-at-least-32-chars",
      BFF_COOKIE_SECURE: "true",
      NODE_ENV: "production",
    });
    expect(config.cookieSecure).toBe(true);
  });

  it("rejects public backend API URL in production", () => {
    expect(() =>
      readConfig({
        OKR_BACKEND_API_URL: "https://backend.example.com:8100",
        OKR_BACKEND_SERVICE_TOKEN: "svc-token-with-more-than-24-chars",
        OKR_BACKEND_SIGNING_SECRET: "signing-secret-that-is-longer-than-thirty-two",
        BFF_SESSION_SECRET: "a-very-secure-session-secret-that-is-at-least-32-chars",
        NODE_ENV: "production",
      }),
    ).toThrow(/private backend host/i);
  });

  it("accepts internal backend API hostnames in production", () => {
    expect(() =>
      readConfig({
        OKR_BACKEND_API_URL: "http://backend-api.ns.svc.cluster.local:8100",
        OKR_BACKEND_SERVICE_TOKEN: "svc-token-with-more-than-24-chars",
        OKR_BACKEND_SIGNING_SECRET: "signing-secret-that-is-longer-than-thirty-two",
        BFF_SESSION_SECRET: "a-very-secure-session-secret-that-is-at-least-32-chars",
        NODE_ENV: "production",
      }),
    ).not.toThrow();
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
