import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

import { proxyToBff } from "@/lib/bff-proxy";

const TARGET = "https://bff.internal/session/me";

function makeRequest(headers: Record<string, string> = {}): NextRequest {
  return new NextRequest("https://app.local/api/session/me?token=QUERY_SECRET", {
    method: "POST",
    headers: {
      cookie: "okr_session=COOKIE_SECRET",
      authorization: "Bearer AUTH_SECRET",
      ...headers,
    },
  });
}

describe("proxyToBff", () => {
  const originalFetch = globalThis.fetch;
  const logged: string[] = [];
  let errorSpy: { mockRestore: () => void };

  beforeEach(() => {
    logged.length = 0;
    errorSpy = vi.spyOn(console, "error").mockImplementation((...args) => {
      logged.push(args.map((value) => String(value)).join(" "));
    });
  });

  afterEach(() => {
    errorSpy.mockRestore();
    globalThis.fetch = originalFetch;
  });

  it("returns the same generic 502 when the upstream fetch fails", async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new TypeError("fetch failed"));

    const response = await proxyToBff(makeRequest(), TARGET);

    expect(response.status).toBe(502);
    await expect(response.json()).resolves.toEqual({ error: "BFF request failed." });
  });

  it("records a structured log line for a failed proxy", async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new TypeError("fetch failed"));

    await proxyToBff(makeRequest(), TARGET);

    expect(logged).toHaveLength(1);
    const payload = JSON.parse(logged[0] ?? "{}") as Record<string, unknown>;
    expect(payload.event).toBe("spa_web_bff_proxy_error");
    expect(payload.method).toBe("POST");
    expect(payload.route).toBe("/api/session/me");
    expect(payload.status).toBe(502);
    expect(payload.target).toBe("/session/me");
    expect(payload.error_type).toBe("TypeError");
    expect(payload.error_message).toBe("fetch failed");
    expect(Number.isNaN(Date.parse(String(payload.ts)))).toBe(false);
  });

  it("includes a cause code when the runtime provides one", async () => {
    const failure = new TypeError("fetch failed");
    (failure as { cause?: unknown }).cause = { code: "ECONNREFUSED" };
    globalThis.fetch = vi.fn().mockRejectedValue(failure);

    await proxyToBff(makeRequest(), TARGET);

    const payload = JSON.parse(logged[0] ?? "{}") as Record<string, unknown>;
    expect(payload.error_code).toBe("ECONNREFUSED");
  });

  it("never writes cookies, authorization or query values into the log", async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new TypeError("fetch failed"));

    await proxyToBff(makeRequest(), TARGET);

    expect(logged).toHaveLength(1);
    expect(logged[0]).not.toContain("COOKIE_SECRET");
    expect(logged[0]).not.toContain("AUTH_SECRET");
    expect(logged[0]).not.toContain("QUERY_SECRET");
  });

  it("does not log when the proxy succeeds", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response("{}", {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    const response = await proxyToBff(makeRequest(), TARGET);

    expect(response.status).toBe(200);
    expect(logged).toHaveLength(0);
  });

  it("forwards the private client IP header when it is present", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response("{}"));
    globalThis.fetch = fetchMock;

    await proxyToBff(makeRequest({ "x-okr-client-ip": "203.0.113.10" }), TARGET);

    const init = fetchMock.mock.calls[0]?.[1];
    expect(new Headers(init?.headers).get("x-okr-client-ip")).toBe("203.0.113.10");
  });

  it("keeps the private client IP header absent when the request does not include it", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response("{}"));
    globalThis.fetch = fetchMock;

    await proxyToBff(makeRequest(), TARGET);

    const init = fetchMock.mock.calls[0]?.[1];
    expect(new Headers(init?.headers).has("x-okr-client-ip")).toBe(false);
  });

  it("does not forward caller-supplied X-Forwarded-For or X-Real-IP headers", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response("{}"));
    globalThis.fetch = fetchMock;

    await proxyToBff(
      makeRequest({
        "x-okr-client-ip": "203.0.113.10",
        "x-forwarded-for": "198.51.100.77",
        "x-real-ip": "192.0.2.44",
      }),
      TARGET,
    );

    const init = fetchMock.mock.calls[0]?.[1];
    const forwardedHeaders = new Headers(init?.headers);
    expect(forwardedHeaders.get("x-okr-client-ip")).toBe("203.0.113.10");
    expect(forwardedHeaders.has("x-forwarded-for")).toBe(false);
    expect(forwardedHeaders.has("x-real-ip")).toBe(false);
  });
});
