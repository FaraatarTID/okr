import { describe, expect, it, vi, beforeEach } from "vitest";

import { readBackendQuery } from "@/lib/api/atlas";

describe("readBackendQuery", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
    globalThis.fetch = originalFetch;
  });

  it("retries transient network failures before succeeding", async () => {
    const fetchMock = vi.fn()
      .mockRejectedValueOnce(new Error("fetch failed"))
      .mockResolvedValueOnce(new Response(JSON.stringify({ users: [{ id: 1 }] }), { status: 200 }));
    globalThis.fetch = fetchMock;

    const payload = await readBackendQuery({
      actor_username: "alice",
      kind: "users.all",
    });

    expect(payload.users).toEqual([{ id: 1 }]);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("retries transient read-query responses before succeeding", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response("backend busy", { status: 503 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ teams: [{ id: 2 }] }), { status: 200 }));
    globalThis.fetch = fetchMock;

    const payload = await readBackendQuery({
      actor_username: "alice",
      kind: "teams.all",
    });

    expect(payload.teams).toEqual([{ id: 2 }]);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
