import { describe, expect, it, vi, beforeEach } from "vitest";

import { readBackendQuery, readCyclesQuery } from "@/lib/api/atlas";

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

// Both read paths used to own their own timeout helper, which is the reason
// `perAttemptTimeoutMs` inside retryWithFetch was never read. The deadline now
// lives in the helper and can only reach the network if the signal is forwarded
// to fetch, so that is asserted here instead of being left to review.
describe("read paths forward the per-attempt abort signal", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
    globalThis.fetch = originalFetch;
  });

  it("forwards an AbortSignal for readCyclesQuery", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ cycles: [] }), { status: 200 }));
    globalThis.fetch = fetchMock;

    await readCyclesQuery({ actor_username: "alice", kind: "cycles.all" });

    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(typeof init.signal?.addEventListener).toBe("function");
    expect(init.signal?.aborted).toBe(false);
  });

  it("forwards an AbortSignal for readBackendQuery", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ users: [] }), { status: 200 }));
    globalThis.fetch = fetchMock;

    await readBackendQuery({ actor_username: "alice", kind: "users.all" });

    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(typeof init.signal?.addEventListener).toBe("function");
    expect(init.signal?.aborted).toBe(false);
  });
});
