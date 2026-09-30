import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "@/lib/api";
import type { AuthUser } from "@/lib/api";
import useSnapshotLifecycle from "@/components/atlas-shell/useSnapshotLifecycle";

vi.mock("@/lib/api", () => ({
  readAtlasSnapshot: vi.fn(),
}));

const baseUser: AuthUser = {
  id: 1,
  username: "alice",
  display_name: "Alice",
  role: "member",
};

describe("useSnapshotLifecycle", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
    vi.useRealTimers();
  });

  it("loads snapshot for a user with parsed cycle context", async () => {
    const readAtlasSnapshotMock = vi.mocked(api.readAtlasSnapshot);
    readAtlasSnapshotMock.mockResolvedValue({ roots: [], index: {}, users_map: {} } as never);

    const { result } = renderHook(() =>
      useSnapshotLifecycle({
        user: baseUser,
        mode: "dashboard",
        parsedCycleId: 12,
        ownerIds: [1, 2],
        ownerIdsError: "",

      }),
    );

    await act(async () => {
      await result.current.loadSnapshotForUser(baseUser);
    });

    expect(readAtlasSnapshotMock).toHaveBeenCalledWith(
      expect.objectContaining({
        actor_username: "alice",
        cycle_id: 12,
        owner_ids: [1, 2],
      }),
    );
    expect(result.current.snapshotPayload).not.toBeNull();
  });


  it("keeps the same snapshot object when a reload returns identical data", async () => {
    const readAtlasSnapshotMock = vi.mocked(api.readAtlasSnapshot);
    readAtlasSnapshotMock.mockImplementation(async () => ({ roots: [1], index: {}, users_map: {} }) as never);

    const { result } = renderHook(() =>
      useSnapshotLifecycle({ user: baseUser, mode: "dashboard", parsedCycleId: 12, ownerIds: [1], ownerIdsError: "" }),
    );
    await act(async () => { await result.current.loadSnapshotForUser(baseUser); });
    const first = result.current.snapshotPayload;
    expect(first).not.toBeNull();

    await act(async () => { await result.current.loadSnapshotForUser(baseUser); });
    expect(result.current.snapshotPayload).toBe(first);

    readAtlasSnapshotMock.mockImplementation(async () => ({ roots: [1, 2], index: {}, users_map: {} }) as never);
    await act(async () => { await result.current.loadSnapshotForUser(baseUser); });
    expect(result.current.snapshotPayload).not.toBe(first);
    expect((result.current.snapshotPayload as unknown as { roots: number[] }).roots).toEqual([1, 2]);
  });  it("clears snapshot payload on explicit clear", async () => {
    const readAtlasSnapshotMock = vi.mocked(api.readAtlasSnapshot);
    readAtlasSnapshotMock.mockResolvedValue({ roots: [], index: {}, users_map: {} } as never);

    const { result } = renderHook(() =>
      useSnapshotLifecycle({
        user: baseUser,
        mode: "dashboard",
        parsedCycleId: 9,
        ownerIds: undefined,
        ownerIdsError: "",

      }),
    );

    await act(async () => {
      await result.current.loadSnapshotForUser(baseUser);
    });
    expect(result.current.snapshotPayload).not.toBeNull();

    act(() => {
      result.current.clearSnapshot();
    });
    expect(result.current.snapshotPayload).toBeNull();
  });

  it("does not request snapshot when cycle is unresolved", async () => {
    const readAtlasSnapshotMock = vi.mocked(api.readAtlasSnapshot);

    const { result } = renderHook(() =>
      useSnapshotLifecycle({
        user: baseUser,
        mode: "dashboard",
        parsedCycleId: null,
        ownerIds: undefined,
        ownerIdsError: "",

      }),
    );

    await act(async () => {
      await result.current.loadSnapshotForUser(baseUser);
    });

    expect(readAtlasSnapshotMock).not.toHaveBeenCalled();
    expect(result.current.snapshotPayload).toBeNull();
  });

  it("ignores a stale snapshot response after switching cycles", async () => {
    const readAtlasSnapshotMock = vi.mocked(api.readAtlasSnapshot);
    let resolveFirst: ((value: never) => void) | undefined;
    let resolveSecond: ((value: never) => void) | undefined;
    readAtlasSnapshotMock
      .mockImplementationOnce(
        () => new Promise((resolve) => {
          resolveFirst = resolve;
        }),
      )
      .mockImplementationOnce(
        () => new Promise((resolve) => {
          resolveSecond = resolve;
        }),
      );

    const { result } = renderHook(() =>
      useSnapshotLifecycle({
        user: baseUser,
        mode: "atlas",
        parsedCycleId: 1,
        ownerIds: undefined,
        ownerIdsError: "",
      }),
    );

    let firstLoad: Promise<void>;
    let secondLoad: Promise<void>;
    await act(async () => {
      firstLoad = result.current.loadSnapshotForUser(baseUser);
      await Promise.resolve();
    });
    await act(async () => {
      // Both loads are awaited at the end of the test. Their responses are
      // resolved out of order below, which is the behaviour under test.
      secondLoad = result.current.loadSnapshotForUser(baseUser);
      await Promise.resolve();
    });

    const managerSnapshot = { goals: [{ id: 2 }], users_map: {} } as never;
    const oldSnapshot = { goals: [{ id: 1 }], users_map: {} } as never;
    await act(async () => {
      resolveSecond?.(managerSnapshot);
      await Promise.resolve();
    });
    expect(result.current.snapshotPayload).toEqual(managerSnapshot);

    await act(async () => {
      resolveFirst?.(oldSnapshot);
      await Promise.resolve();
    });
    expect(result.current.snapshotPayload).toEqual(managerSnapshot);
    await firstLoad!;
    await secondLoad!;
  });

  it("keeps one polling interval across mode changes and polls only with current Atlas mode", async () => {
    vi.useFakeTimers();
    const readAtlasSnapshotMock = vi.mocked(api.readAtlasSnapshot);
    readAtlasSnapshotMock.mockResolvedValue({ roots: [], index: {}, users_map: {} } as never);
    const setIntervalSpy = vi.spyOn(window, "setInterval");
    const clearIntervalSpy = vi.spyOn(window, "clearInterval");
    const ownerIds = [1, 2];
    const pollTimerIds = () =>
      setIntervalSpy.mock.calls.flatMap(([, delay], index) =>
        delay === 45_000 ? [setIntervalSpy.mock.results[index]?.value] : [],
      );
    const clearedPollIntervals = () =>
      clearIntervalSpy.mock.calls.filter(([timer]) => pollTimerIds().includes(timer));

    const { rerender, unmount } = renderHook(
      ({ mode }) =>
        useSnapshotLifecycle({
          user: baseUser,
          mode,
          parsedCycleId: 12,
          ownerIds,
          ownerIdsError: "",
        }),
      { initialProps: { mode: "atlas" } },
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(pollTimerIds()).toHaveLength(1);
    expect(readAtlasSnapshotMock).toHaveBeenCalledWith(
      expect.objectContaining({ include_analysis: true }),
    );
    readAtlasSnapshotMock.mockClear();

    rerender({ mode: "dashboard" });
    expect(pollTimerIds()).toHaveLength(1);
    expect(clearedPollIntervals()).toHaveLength(0);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(readAtlasSnapshotMock).toHaveBeenCalledWith(
      expect.objectContaining({ include_analysis: false }),
    );
    readAtlasSnapshotMock.mockClear();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(45_000);
    });
    expect(readAtlasSnapshotMock).not.toHaveBeenCalled();

    rerender({ mode: "atlas" });
    expect(pollTimerIds()).toHaveLength(1);
    expect(clearedPollIntervals()).toHaveLength(0);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(readAtlasSnapshotMock).toHaveBeenCalledWith(
      expect.objectContaining({ include_analysis: true }),
    );
    readAtlasSnapshotMock.mockClear();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(45_000);
    });
    expect(readAtlasSnapshotMock).toHaveBeenCalledTimes(1);
    expect(readAtlasSnapshotMock).toHaveBeenCalledWith(
      expect.objectContaining({ include_analysis: true }),
    );

    unmount();
    expect(clearedPollIntervals()).toHaveLength(1);
  });
});
