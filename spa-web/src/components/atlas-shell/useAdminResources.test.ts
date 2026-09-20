import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "@/lib/api";
import type { AuthUser } from "@/lib/api";
import useAdminResources from "@/components/atlas-shell/useAdminResources";
import { clearResourceCache } from "@/lib/resourceCache";

vi.mock("@/lib/api", () => ({
  readAdminAiHealth: vi.fn(),
  readAdminPdfHealth: vi.fn(),
  readAuditSummary: vi.fn(),
  readBackendQuery: vi.fn(),
  readCyclesQuery: vi.fn(),
}));

const baseUser: AuthUser = {
  id: 1,
  username: "alice",
  display_name: "Alice",
  role: "admin",
};

describe("useAdminResources", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
    // The cycle read is cached per username, and every test in this file uses
    // the same user, so the cache must be dropped between tests or a later test
    // would be served the previous test's value instead of exercising the API.
    clearResourceCache();
  });

  it("loads cycles/users/teams with stable sorting", async () => {
    const readCyclesQueryMock = vi.mocked(api.readCyclesQuery);
    const readBackendQueryMock = vi.mocked(api.readBackendQuery);
    readCyclesQueryMock.mockResolvedValue([
      { id: 2, title: "Cycle 2" },
      { id: 9, title: "Cycle 9" },
    ] as never);
    readBackendQueryMock
      .mockResolvedValueOnce({
        users: [
          { id: 2, username: "zoe" },
          { id: 1, username: "alice" },
        ],
      } as never)
      .mockResolvedValueOnce({
        teams: [
          { id: 2, name: "Platform" },
          { id: 1, name: "AI" },
        ],
      } as never);

    const { result } = renderHook(() => useAdminResources());

    await act(async () => {
      await result.current.loadAdminResources(baseUser);
    });

    expect(result.current.adminCycles.map((row) => row.id)).toEqual([9, 2]);
    expect(result.current.adminUsers.map((row) => row.username)).toEqual(["alice", "zoe"]);
    expect(result.current.adminTeams.map((row) => row.name)).toEqual(["AI", "Platform"]);
    expect(result.current.adminCycleError).toBe("");
    expect(result.current.adminDataError).toBe("");
  });

  it("captures data-load failure and clears collections", async () => {
    const readCyclesQueryMock = vi.mocked(api.readCyclesQuery);
    const readBackendQueryMock = vi.mocked(api.readBackendQuery);
    readCyclesQueryMock.mockRejectedValue(new Error("cycles unavailable"));
    readBackendQueryMock.mockRejectedValue(new Error("users unavailable"));

    const { result } = renderHook(() => useAdminResources());

    await act(async () => {
      await result.current.loadAdminResources(baseUser);
    });

    expect(result.current.adminCycles).toEqual([]);
    expect(result.current.adminUsers).toEqual([]);
    expect(result.current.adminTeams).toEqual([]);
    expect(result.current.adminCycleError).toContain("cycles unavailable");
    expect(result.current.adminDataError).toContain("users unavailable");
  });

  it("loads admin ai/pdf health payloads and clears pending state", async () => {
    const readAdminAiHealthMock = vi.mocked(api.readAdminAiHealth);
    const readAdminPdfHealthMock = vi.mocked(api.readAdminPdfHealth);
    readAdminAiHealthMock.mockResolvedValue({
      ok: true,
      provider: "gemini",
    } as never);
    readAdminPdfHealthMock.mockResolvedValue({
      ok: true,
      backend: "wkhtmltopdf",
    } as never);

    const { result } = renderHook(() => useAdminResources());

    await act(async () => {
      await result.current.loadAdminHealth(baseUser, false);
    });

    expect(readAdminAiHealthMock).toHaveBeenCalledWith(
      expect.objectContaining({ actor_username: "alice", live_probe: false }),
    );
    expect(readAdminPdfHealthMock).toHaveBeenCalledWith(
      expect.objectContaining({ actor_username: "alice" }),
    );
    expect(result.current.adminAiHealth).toEqual(expect.objectContaining({ provider: "gemini" }));
    expect(result.current.adminPdfHealth).toEqual(expect.objectContaining({ backend: "wkhtmltopdf" }));
    expect(result.current.adminHealthPending).toBe(false);
  });

  it("loads audit summary payloads and clears pending state", async () => {
    const readAuditSummaryMock = vi.mocked(api.readAuditSummary);
    readAuditSummaryMock.mockResolvedValue({
      total_events: 12,
      success_events: 10,
      failure_events: 2,
      recent_events: [],
    } as never);

    const { result } = renderHook(() => useAdminResources());

    await act(async () => {
      await result.current.loadAdminAuditSummary(baseUser);
    });

    expect(readAuditSummaryMock).toHaveBeenCalledWith(
      expect.objectContaining({ actor_username: "alice", days: 30, recent_limit: 10 }),
    );
    expect(result.current.adminAuditSummary).toEqual(expect.objectContaining({ total_events: 12 }));
    expect(result.current.adminAuditSummaryPending).toBe(false);
    expect(result.current.adminAuditSummaryError).toBe("");
  });

  it("reuses the cached users/teams pair within the TTL", async () => {
    const readBackendQueryMock = vi.mocked(api.readBackendQuery);
    vi.mocked(api.readCyclesQuery).mockResolvedValue([] as never);
    readBackendQueryMock
      .mockResolvedValueOnce({ users: [{ id: 1, username: "alice" }] } as never)
      .mockResolvedValueOnce({ teams: [{ id: 1, name: "AI" }] } as never);

    const { result } = renderHook(() => useAdminResources());

    await act(async () => {
      await result.current.loadAdminUsersAndTeams(baseUser);
    });
    expect(readBackendQueryMock).toHaveBeenCalledTimes(2);

    // Re-entering the admin panel inside the TTL must not refetch the pair.
    await act(async () => {
      await result.current.loadAdminUsersAndTeams(baseUser);
    });

    expect(readBackendQueryMock).toHaveBeenCalledTimes(2);
    expect(result.current.adminUsers.map((row) => row.username)).toEqual(["alice"]);
    expect(result.current.adminTeams.map((row) => row.name)).toEqual(["AI"]);
  });

  it("re-reads the pair when the caller bypasses the cache", async () => {
    const readBackendQueryMock = vi.mocked(api.readBackendQuery);
    vi.mocked(api.readCyclesQuery).mockResolvedValue([] as never);
    readBackendQueryMock.mockResolvedValue({ users: [], teams: [] } as never);

    const { result } = renderHook(() => useAdminResources());

    await act(async () => {
      await result.current.loadAdminUsersAndTeams(baseUser);
    });
    readBackendQueryMock.mockClear();
    await act(async () => {
      await result.current.loadAdminUsersAndTeams(baseUser, { bypassCache: true });
    });

    expect(readBackendQueryMock).toHaveBeenCalledTimes(2);
  });

  it("caches the cycle read so admin entry does not re-request it", async () => {
    const readCyclesQueryMock = vi.mocked(api.readCyclesQuery);
    vi.mocked(api.readBackendQuery).mockResolvedValue({ users: [], teams: [] } as never);
    readCyclesQueryMock.mockResolvedValue([{ id: 7, title: "Cycle 7" }] as never);

    const { result } = renderHook(() => useAdminResources());

    await act(async () => {
      await result.current.loadAdminCycles(baseUser);
    });
    expect(readCyclesQueryMock).toHaveBeenCalledTimes(2);

    await act(async () => {
      await result.current.loadAdminCycles(baseUser);
    });

    expect(readCyclesQueryMock).toHaveBeenCalledTimes(2);
  });
});
