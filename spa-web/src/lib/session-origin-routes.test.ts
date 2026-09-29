// @vitest-environment node
//
// Route-level proof that the origin guard is actually wired in. The unit tests for
// `classifyOrigin` cannot catch a handler that forgets to call it.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

import { POST as loginPost } from "@/app/api/session/login/route";
import { POST as logoutPost } from "@/app/api/session/logout/route";
import {
  DELETE as backendDelete,
  GET as backendGet,
  POST as backendPost,
} from "@/app/api/backend/[...path]/route";

const HOST = "app.example";

function req(path: string, method: string, entries: Record<string, string>): NextRequest {
  return new NextRequest(`https://${HOST}${path}`, {
    method,
    headers: { host: HOST, ...entries },
    ...(method === "GET" ? {} : { body: "{}" }),
  });
}

const CROSS = { origin: "https://evil.example" };
const SAME = { origin: `https://${HOST}` };
const ctx = { params: Promise.resolve({ path: ["v1", "jobs"] }) };

describe("origin guard wiring", () => {
  const originalFetch = globalThis.fetch;
  let fetchMock: ReturnType<typeof vi.fn>;
  let warnSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    warnSpy = vi.spyOn(console, "warn").mockImplementation(() => undefined);
  });

  afterEach(() => {
    warnSpy.mockRestore();
    globalThis.fetch = originalFetch;
  });

  it("refuses a cross-origin login before it reaches the BFF", async () => {
    const response = await loginPost(req("/api/session/login", "POST", CROSS));

    expect(response.status).toBe(403);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("forwards a same-origin login to the BFF", async () => {
    // Positive control: without it the rejection above passes just as well if the
    // handler rejected everything.
    const response = await loginPost(req("/api/session/login", "POST", SAME));

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("forwards a login with no Origin or Fetch-Metadata, as a non-browser probe sends", async () => {
    const response = await loginPost(req("/api/session/login", "POST", {}));

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("refuses a cross-site logout before it reaches the BFF", async () => {
    const response = await logoutPost(
      req("/api/session/logout", "POST", { "sec-fetch-site": "cross-site" }),
    );

    expect(response.status).toBe(403);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("forwards a same-origin logout to the BFF", async () => {
    const response = await logoutPost(
      req("/api/session/logout", "POST", { "sec-fetch-site": "same-origin" }),
    );

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("refuses cross-origin state-changing calls on the proxied backend route", async () => {
    for (const handler of [backendPost, backendDelete]) {
      const response = await handler(req("/api/backend/v1/jobs", "POST", CROSS), ctx);
      expect(response.status).toBe(403);
    }
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("leaves GET on the proxied backend route unguarded", async () => {
    // Safe methods are exempt by design; a cross-origin read cannot change state.
    const response = await backendGet(req("/api/backend/v1/jobs", "GET", CROSS), ctx);

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("forwards a same-origin state-changing call on the proxied backend route", async () => {
    const response = await backendPost(req("/api/backend/v1/jobs", "POST", SAME), ctx);

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
