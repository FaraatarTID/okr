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

  it("clears snapshot payload on explicit clear", async () => {
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
    await act(async () => {
      firstLoad = result.current.loadSnapshotForUser(baseUser);
      await Promise.resolve();
    });
    await act(async () => {
      result.current.loadSnapshotForUser(baseUser);
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
  });
});
