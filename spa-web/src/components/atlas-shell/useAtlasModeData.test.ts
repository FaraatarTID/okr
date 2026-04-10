import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "@/lib/api";
import type { AuthUser } from "@/lib/api/auth";
import useAtlasModeData from "@/components/atlas-shell/useAtlasModeData";

vi.mock("@/lib/api", () => ({
  readBackendQuery: vi.fn(),
}));

const baseUser: AuthUser = {
  id: 1,
  username: "alice",
  display_name: "Alice",
  role: "admin",
};

describe("useAtlasModeData", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
  });

  it("loads weekly mode payloads and updates weekly draft projection", async () => {
    const readBackendQueryMock = vi.mocked(api.readBackendQuery);
    const setWeeklyDraft = vi.fn();
    const setRetroDraft = vi.fn();
    const loadLeadershipMetricsSnapshot = vi.fn().mockResolvedValue(null);

    readBackendQueryMock
      .mockResolvedValueOnce({
        weekly_plan: {
          id: 9,
          user_id: 1,
          week_start_date: "2026-02-23",
          week_end_date: "2026-03-01",
          priority_1: "Ship SPA auth",
          priority_2: "Harden CI gates",
          priority_3: null,
          is_active: true,
        },
      } as never)
      .mockResolvedValueOnce({
        work_logs: [{ id: 1, duration_minutes: 25 }],
      } as never)
      .mockResolvedValueOnce({
        key_results: [{ id: 5, title: "KR 5" }],
      } as never)
      .mockResolvedValueOnce({
        experiments: [{ id: 3, key_result_id: 5, cycle_id: 7 }],
      } as never);

    const { result } = renderHook(() =>
      useAtlasModeData({
        mode: "atlas",
        user: baseUser,
        parsedCycleId: 7,
        setWeeklyDraft,
        setRetroDraft,
        loadLeadershipMetricsSnapshot,
      }),
    );

    await act(async () => {
      await result.current.loadModeData(baseUser, "weekly");
    });

    expect(readBackendQueryMock).toHaveBeenCalledTimes(4);
    expect(readBackendQueryMock).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({ kind: "weekly_plan.active" }),
    );
    expect(readBackendQueryMock).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({ kind: "work_logs.by_range" }),
    );
    expect(result.current.weeklyPlanData?.id).toBe(9);
    expect(result.current.weeklyLogs).toHaveLength(1);
    expect(result.current.weeklyKrsNeedingCheckIn).toHaveLength(1);
    expect(result.current.weeklyReviewExperiments).toHaveLength(1);
    expect(setWeeklyDraft).toHaveBeenCalledWith({
      p1: "Ship SPA auth",
      p2: "Harden CI gates",
      p3: "",
    });
  });

  it("loads dashboard mode and requests leadership metrics refresh", async () => {
    const readBackendQueryMock = vi.mocked(api.readBackendQuery);
    const setWeeklyDraft = vi.fn();
    const setRetroDraft = vi.fn();
    const loadLeadershipMetricsSnapshot = vi.fn().mockResolvedValue(null);

    readBackendQueryMock
      .mockResolvedValueOnce({
        tasks: [{ id: 11, title: "Task 11", status: "DONE", progress: 100 }],
      } as never)
      .mockResolvedValueOnce({
        work_logs: [{ id: 1, duration_minutes: 42 }],
      } as never);

    const { result } = renderHook(() =>
      useAtlasModeData({
        mode: "atlas",
        user: baseUser,
        parsedCycleId: 7,
        setWeeklyDraft,
        setRetroDraft,
        loadLeadershipMetricsSnapshot,
      }),
    );

    await act(async () => {
      await result.current.loadModeData(baseUser, "dashboard");
    });

    expect(result.current.timelineTasks).toHaveLength(1);
    expect(result.current.timelineLogs).toHaveLength(1);
    expect(loadLeadershipMetricsSnapshot).toHaveBeenCalledWith(baseUser);
  });

  it("guards dashboard/timeline refresh from overlapping in-flight calls", async () => {
    const readBackendQueryMock = vi.mocked(api.readBackendQuery);
    const setWeeklyDraft = vi.fn();
    const setRetroDraft = vi.fn();
    const loadLeadershipMetricsSnapshot = vi.fn().mockResolvedValue(null);

    readBackendQueryMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          setTimeout(() => resolve({ tasks: [], work_logs: [] }), 5);
        }) as never,
    );

    const { result } = renderHook(() =>
      useAtlasModeData({
        mode: "atlas",
        user: baseUser,
        parsedCycleId: 7,
        setWeeklyDraft,
        setRetroDraft,
        loadLeadershipMetricsSnapshot,
      }),
    );

    const run1 = result.current.refreshDashboardModeData(baseUser, "timeline");
    const run2 = result.current.refreshDashboardModeData(baseUser, "timeline");

    await act(async () => {
      await Promise.all([run1, run2]);
    });
    expect(readBackendQueryMock).toHaveBeenCalledTimes(2);
  });

  it("auto-loads mode data when user enters non-atlas/non-admin mode", async () => {
    const readBackendQueryMock = vi.mocked(api.readBackendQuery);
    const setWeeklyDraft = vi.fn();
    const setRetroDraft = vi.fn();
    const loadLeadershipMetricsSnapshot = vi.fn().mockResolvedValue(null);

    readBackendQueryMock.mockImplementation(async (payload) => {
      if (payload.kind === "weekly_plan.active") {
        return { weekly_plan: null } as never;
      }
      if (payload.kind === "work_logs.by_range") {
        return { work_logs: [{ id: 1, duration_minutes: 30 }] } as never;
      }
      return {} as never;
    });

    const { result } = renderHook(() =>
      useAtlasModeData({
        mode: "weekly",
        user: baseUser,
        parsedCycleId: null,
        setWeeklyDraft,
        setRetroDraft,
        loadLeadershipMetricsSnapshot,
      }),
    );

    await waitFor(() =>
      expect(readBackendQueryMock).toHaveBeenCalledWith(
        expect.objectContaining({ kind: "weekly_plan.active" }),
      ),
    );
    await waitFor(() => expect(result.current.weeklyLogs).toHaveLength(1));
    expect(result.current.modeDataPending).toBe(false);
  });
});
