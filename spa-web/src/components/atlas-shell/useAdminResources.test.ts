import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "@/lib/api";
import type { AuthUser } from "@/lib/api";
import * as adminResourcesModule from "@/lib/adminResources";
import * as cyclesModule from "@/lib/cycles";
import useAdminResources from "@/components/atlas-shell/useAdminResources";

/**
 * The cache-backed reads are mocked at their module boundary on purpose.
 *
 * Driving the real cache from here is module state shared across tests and is not
 * deterministic (an earlier version of this file served one test's payload to
 * another). The cache is covered directly in `src/lib/resourceCache.test.ts`, and
 * these tests own what the hook does with the pair it receives: publishing it,
 * sorting it, clearing it on failure, and asking for a bypass when the caller
 * needs fresh data.
 */
vi.mock("@/lib/api", () => ({
  readAdminAiHealth: vi.fn(),
  readAdminPdfHealth: vi.fn(),
  readAuditSummary: vi.fn(),
}));

vi.mock("@/lib/cycles", () => ({
  readMergedCycles: vi.fn(),
}));

vi.mock("@/lib/adminResources", () => ({
  readSortedAdminResources: vi.fn(),
}));

const baseUser: AuthUser = {
  id: 1,
  username: "alice",
  display_name: "Alice",
  role: "admin",
};

const readMergedCyclesMock = () => vi.mocked(cyclesModule.readMergedCycles);
const readSortedAdminMock = () => vi.mocked(adminResourcesModule.readSortedAdminResources);

describe("useAdminResources", () => {
  beforeEach(() => {
    vi.mocked(api.readAdminAiHealth).mockReset();
    vi.mocked(api.readAdminPdfHealth).mockReset();
    vi.mocked(api.readAuditSummary).mockReset();
    readMergedCyclesMock().mockReset();
    readSortedAdminMock().mockReset();
  });

  it("loads cycles/users/teams with stable sorting", async () => {
    readMergedCyclesMock().mockResolvedValue([
      { id: 9, title: "Cycle 9" },
      { id: 2, title: "Cycle 2" },
    ] as never);
    readSortedAdminMock().mockResolvedValue({
      users: [{ id: 1, username: "alice" }, { id: 2, username: "zoe" }],
      teams: [{ id: 1, name: "AI" }, { id: 2, name: "Platform" }],
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
    readMergedCyclesMock().mockRejectedValue(new Error("cycles unavailable"));
    readSortedAdminMock().mockRejectedValue(new Error("users unavailable"));

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

  it("publishes the users/teams pair it receives", async () => {
    readSortedAdminMock().mockResolvedValue({
      users: [{ id: 1, username: "alice" }],
      teams: [{ id: 1, name: "AI" }],
    } as never);

    const { result } = renderHook(() => useAdminResources());

    await act(async () => {
      await result.current.loadAdminUsersAndTeams(baseUser);
    });

    expect(result.current.adminUsers.map((row) => row.username)).toEqual(["alice"]);
    expect(result.current.adminTeams.map((row) => row.name)).toEqual(["AI"]);
    expect(result.current.adminDataPending).toBe(false);
  });

  it("asks for a cache bypass when the caller needs fresh users/teams", async () => {
    readSortedAdminMock().mockResolvedValue({ users: [], teams: [] } as never);

    const { result } = renderHook(() => useAdminResources());

    await act(async () => {
      await result.current.loadAdminUsersAndTeams(baseUser);
    });
    expect(readSortedAdminMock()).toHaveBeenLastCalledWith("alice", {
      bypassCache: undefined,
    });

    await act(async () => {
      await result.current.loadAdminUsersAndTeams(baseUser, { bypassCache: true });
    });
    expect(readSortedAdminMock()).toHaveBeenLastCalledWith("alice", {
      bypassCache: true,
    });
  });

  it("asks for a cache bypass when the caller needs fresh cycles", async () => {
    readMergedCyclesMock().mockResolvedValue([] as never);

    const { result } = renderHook(() => useAdminResources());

    await act(async () => {
      await result.current.loadAdminCycles(baseUser, { bypassCache: true });
    });

    expect(readMergedCyclesMock()).toHaveBeenCalledWith("alice", {
      bypassCache: true,
    });
  });

  it("clears the pending flag when the users/teams read fails", async () => {
    readSortedAdminMock().mockRejectedValue(new Error("teams unavailable"));

    const { result } = renderHook(() => useAdminResources());

    await act(async () => {
      await result.current.loadAdminUsersAndTeams(baseUser);
    });

    expect(result.current.adminDataPending).toBe(false);
    expect(result.current.adminDataError).toContain("teams unavailable");
  });

  it("loads admin ai/pdf health payloads and clears pending state", async () => {
    vi.mocked(api.readAdminAiHealth).mockResolvedValue({
      ok: true,
      provider: "gemini",
    } as never);
    vi.mocked(api.readAdminPdfHealth).mockResolvedValue({
      ok: true,
      backend: "wkhtmltopdf",
    } as never);

    const { result } = renderHook(() => useAdminResources());

    await act(async () => {
      await result.current.loadAdminHealth(baseUser, false);
    });

    expect(vi.mocked(api.readAdminAiHealth)).toHaveBeenCalledWith(
      expect.objectContaining({ actor_username: "alice", live_probe: false }),
    );
    expect(vi.mocked(api.readAdminPdfHealth)).toHaveBeenCalledWith(
      expect.objectContaining({ actor_username: "alice" }),
    );
    expect(result.current.adminAiHealth).toEqual(expect.objectContaining({ provider: "gemini" }));
    expect(result.current.adminPdfHealth).toEqual(expect.objectContaining({ backend: "wkhtmltopdf" }));
    expect(result.current.adminHealthPending).toBe(false);
  });

  it("loads the admin audit summary", async () => {
    vi.mocked(api.readAuditSummary).mockResolvedValue({ total_events: 12 } as never);

    const { result } = renderHook(() => useAdminResources());

    await act(async () => {
      await result.current.loadAdminAuditSummary(baseUser);
    });

    expect(vi.mocked(api.readAuditSummary)).toHaveBeenCalledWith(
      expect.objectContaining({ actor_username: "alice", days: 30, recent_limit: 10 }),
    );
    expect(result.current.adminAuditSummary).toEqual(expect.objectContaining({ total_events: 12 }));
    expect(result.current.adminAuditSummaryPending).toBe(false);
    expect(result.current.adminAuditSummaryError).toBe("");
  });
});
