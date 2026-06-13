import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "@/lib/api";
import type { AuthUser } from "@/lib/api/auth";
import useTimerSession from "@/components/atlas-shell/useTimerSession";

vi.mock("@/lib/api", () => ({
  startTaskTimer: vi.fn(),
  stopTaskTimer: vi.fn(),
}));

const baseUser: AuthUser = {
  id: 1,
  username: "alice",
  display_name: "Alice",
  role: "admin",
};

describe("useTimerSession", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
  });

  it("starts timer and triggers snapshot/dashboard refresh", async () => {
    const startTaskTimerMock = vi.mocked(api.startTaskTimer);
    const loadSnapshotForUser = vi.fn().mockResolvedValue(undefined);
    const refreshDashboardModeData = vi.fn().mockResolvedValue(undefined);
    startTaskTimerMock.mockResolvedValue({
      task_id: 11,
      start_time: new Date().toISOString(),
    } as never);

    const { result } = renderHook(() =>
      useTimerSession({
        user: baseUser,

        focusTaskId: 11,
        focusTaskStartedAt: "",
        parsedCycleId: 7,
        mode: "dashboard",
        loadSnapshotForUser,
        refreshDashboardModeData,
      }),
    );

    await act(async () => {
      await result.current.handleTimerStart();
    });

    expect(startTaskTimerMock).toHaveBeenCalledWith({
      actor_username: "alice",
      task_id: 11,
    });
    await waitFor(() => expect(result.current.timerModalOpen).toBe(true));
    expect(result.current.focusTaskRunning).toBe(true);
    expect(result.current.timerMessage).toContain("Timer started for task #11");
    expect(loadSnapshotForUser).toHaveBeenCalledWith(baseUser);
    expect(refreshDashboardModeData).toHaveBeenCalledWith(baseUser, "dashboard");
  });

  it("returns actionable error when stop is requested without a resolved task", async () => {
    const stopTaskTimerMock = vi.mocked(api.stopTaskTimer);
    const loadSnapshotForUser = vi.fn().mockResolvedValue(undefined);
    const refreshDashboardModeData = vi.fn().mockResolvedValue(undefined);

    const { result } = renderHook(() =>
      useTimerSession({
        user: baseUser,

        focusTaskId: null,
        focusTaskStartedAt: "",
        parsedCycleId: 7,
        mode: "daily",
        loadSnapshotForUser,
        refreshDashboardModeData,
      }),
    );

    await act(async () => {
      await result.current.handleTimerStop();
    });

    expect(stopTaskTimerMock).not.toHaveBeenCalled();
    expect(result.current.timerError).toBe("No running task timer was found.");
  });

  it("stops timer, clears local session state, and resets summary", async () => {
    const stopTaskTimerMock = vi.mocked(api.stopTaskTimer);
    const loadSnapshotForUser = vi.fn().mockResolvedValue(undefined);
    const refreshDashboardModeData = vi.fn().mockResolvedValue(undefined);
    stopTaskTimerMock.mockResolvedValue({
      task_id: 11,
      duration_minutes: 25,
      start_time: new Date(Date.now() - 25 * 60_000).toISOString(),
      end_time: new Date().toISOString(),
      summary: "completed focus block",
    } as never);

    const { result } = renderHook(() =>
      useTimerSession({
        user: baseUser,

        focusTaskId: 11,
        focusTaskStartedAt: new Date(Date.now() - 5 * 60_000).toISOString(),
        parsedCycleId: 7,
        mode: "timeline",
        loadSnapshotForUser,
        refreshDashboardModeData,
      }),
    );

    act(() => {
      result.current.setTimerSummary("completed focus block");
      result.current.setTimerModalOpen(true);
    });

    await act(async () => {
      await result.current.handleTimerStop();
    });

    expect(stopTaskTimerMock).toHaveBeenCalledWith({
      actor_username: "alice",
      task_id: 11,
      summary: "completed focus block",
    });
    expect(result.current.timerSummary).toBe("");
    expect(result.current.timerModalOpen).toBe(false);
    expect(result.current.timerMessage).toContain("Timer stopped for task #11; duration 25 min.");
    expect(loadSnapshotForUser).toHaveBeenCalledWith(baseUser);
    expect(refreshDashboardModeData).toHaveBeenCalledWith(baseUser, "timeline");
  });
});
