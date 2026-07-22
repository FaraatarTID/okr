import { describe, expect, it, vi, beforeEach } from "vitest";

import * as http from "@/lib/api/http";
import { readBackendQuery } from "@/lib/api/atlas";

vi.mock("@/lib/api/http", () => ({
  fetchWithTimeout: vi.fn(),
  isTransientCycleQueryFailure: vi.fn((status: number) => status >= 500),
  isTransientNetworkError: vi.fn((error: unknown) =>
    String(error instanceof Error ? error.message : error).toLowerCase().includes("timed out"),
  ),
  jsonHeaders: vi.fn(() => ({})),
  responseDetail: vi.fn(async () => "temporary backend outage"),
  waitMs: vi.fn(async () => undefined),
}));

describe("readBackendQuery", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("retries transient network failures before succeeding", async () => {
    const fetchWithTimeoutMock = vi.mocked(http.fetchWithTimeout);
    const waitMsMock = vi.mocked(http.waitMs);

    fetchWithTimeoutMock
      .mockRejectedValueOnce(new Error("timed out"))
      .mockResolvedValueOnce(new Response(JSON.stringify({ users: [{ id: 1 }] }), { status: 200 }));

    const payload = await readBackendQuery({
      actor_username: "alice",
      kind: "users.all",
    });

    expect(payload.users).toEqual([{ id: 1 }]);
    expect(fetchWithTimeoutMock).toHaveBeenCalledTimes(2);
    expect(waitMsMock).toHaveBeenCalledTimes(1);
  });

  it("retries transient read-query responses before succeeding", async () => {
    const fetchWithTimeoutMock = vi.mocked(http.fetchWithTimeout);
    const waitMsMock = vi.mocked(http.waitMs);

    fetchWithTimeoutMock
      .mockResolvedValueOnce(new Response("backend busy", { status: 503 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ teams: [{ id: 2 }] }), { status: 200 }));

    const payload = await readBackendQuery({
      actor_username: "alice",
      kind: "teams.all",
    });

    expect(payload.teams).toEqual([{ id: 2 }]);
    expect(fetchWithTimeoutMock).toHaveBeenCalledTimes(2);
    expect(waitMsMock).toHaveBeenCalledTimes(1);
  });
});
