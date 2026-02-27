import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { AtlasIndexNode } from "@/lib/atlas";
import * as api from "@/lib/api";
import type { AuthUser } from "@/lib/api/auth";
import useInspectorAuxData from "@/components/atlas-shell/useInspectorAuxData";

vi.mock("@/lib/api", () => ({
  readBackendQuery: vi.fn(),
  createAlignmentMutation: vi.fn(),
  deleteAlignmentMutation: vi.fn(),
  deleteWorkLogMutation: vi.fn(),
}));

const baseUser: AuthUser = {
  id: 1,
  username: "alice",
  display_name: "Alice",
  role: "admin",
};

function buildMeta(type: AtlasIndexNode["type"], id: number): AtlasIndexNode {
  return {
    ref: `${type.toLowerCase()}_${id}`,
    id,
    node: {} as AtlasIndexNode["node"],
    type,
    title: `${type} ${id}`,
    titleLower: `${type.toLowerCase()} ${id}`,
    description: "",
    progress: 0,
    depth: 0,
    parent: null,
    path: [`${type.toLowerCase()}_${id}`],
    children: [],
    ownerId: null,
    nodeOwnerId: null,
    timerOwnerId: null,
    ownerName: "Unknown",
  };
}

describe("useInspectorAuxData", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
  });

  it("loads alignment context for selected objective", async () => {
    const readBackendQueryMock = vi.mocked(api.readBackendQuery);
    readBackendQueryMock.mockResolvedValue({
      parents: [{ id: 9, title: "Parent" }],
      children: [],
      all_objectives: [],
      edges: [],
    });
    const selectedMeta = buildMeta("OBJECTIVE", 11);

    const { result } = renderHook(() =>
      useInspectorAuxData({
        user: baseUser,
        selectedMeta,
        rolloutAllowed: true,
        parsedCycleId: null,
        loadSnapshotForUser: vi.fn().mockResolvedValue(undefined),
      }),
    );

    await waitFor(() =>
      expect(readBackendQueryMock).toHaveBeenCalledWith({
        actor_username: "alice",
        kind: "alignments.context",
        params: { objective_id: 11 },
      }),
    );

    await waitFor(() => expect(result.current.alignmentPending).toBe(false));
    expect(result.current.alignmentContext?.parents?.[0]?.id).toBe(9);
  });

  it("exposes alignment error when context load fails", async () => {
    const readBackendQueryMock = vi.mocked(api.readBackendQuery);
    readBackendQueryMock.mockRejectedValue(new Error("alignment load failed"));
    const selectedMeta = buildMeta("OBJECTIVE", 12);

    const { result } = renderHook(() =>
      useInspectorAuxData({
        user: baseUser,
        selectedMeta,
        rolloutAllowed: true,
        parsedCycleId: null,
        loadSnapshotForUser: vi.fn().mockResolvedValue(undefined),
      }),
    );

    await waitFor(() =>
      expect(result.current.alignmentError).toContain("alignment load failed"),
    );
    expect(result.current.alignmentContext).toBeNull();
  });

  it("loads and sorts task work logs by newest date first", async () => {
    const readBackendQueryMock = vi.mocked(api.readBackendQuery);
    readBackendQueryMock.mockResolvedValue({
      work_logs: [
        { id: 2, end_time: "2026-02-27T10:00:00Z", duration_minutes: 10 },
        { id: 1, end_time: "2026-02-27T11:00:00Z", duration_minutes: 20 },
      ],
    });
    const selectedMeta = buildMeta("TASK", 44);

    const { result } = renderHook(() =>
      useInspectorAuxData({
        user: baseUser,
        selectedMeta,
        rolloutAllowed: true,
        parsedCycleId: null,
        loadSnapshotForUser: vi.fn().mockResolvedValue(undefined),
      }),
    );

    await waitFor(() =>
      expect(readBackendQueryMock).toHaveBeenCalledWith({
        actor_username: "alice",
        kind: "work_logs.by_task",
        params: { task_id: 44 },
      }),
    );

    await waitFor(() =>
      expect(result.current.inspectTaskWorkHistoryRows.map((row) => row.id)).toEqual([1, 2]),
    );
    expect(result.current.inspectTaskWorkHistoryRows.map((row) => row.id)).toEqual([1, 2]);
    expect(result.current.inspectTaskWorkLogsError).toBe("");
  });

  it("validates alignment target before create mutation", async () => {
    const readBackendQueryMock = vi.mocked(api.readBackendQuery);
    const createAlignmentMutationMock = vi.mocked(api.createAlignmentMutation);
    readBackendQueryMock.mockResolvedValue({
      parents: [],
      children: [],
      all_objectives: [],
      edges: [],
    });
    const selectedMeta = buildMeta("OBJECTIVE", 55);

    const { result } = renderHook(() =>
      useInspectorAuxData({
        user: baseUser,
        selectedMeta,
        rolloutAllowed: true,
        parsedCycleId: null,
        loadSnapshotForUser: vi.fn().mockResolvedValue(undefined),
      }),
    );

    await waitFor(() => expect(readBackendQueryMock).toHaveBeenCalled());

    await act(async () => {
      await result.current.handleAlignmentCreate();
    });

    expect(result.current.alignmentError).toBe("Choose a valid objective to link.");
    expect(createAlignmentMutationMock).not.toHaveBeenCalled();
  });

  it("runs alignment create and delete flows with refreshed context", async () => {
    const readBackendQueryMock = vi.mocked(api.readBackendQuery);
    const createAlignmentMutationMock = vi.mocked(api.createAlignmentMutation);
    const deleteAlignmentMutationMock = vi.mocked(api.deleteAlignmentMutation);
    readBackendQueryMock.mockResolvedValue({
      parents: [],
      children: [],
      all_objectives: [],
      edges: [],
    });
    createAlignmentMutationMock.mockResolvedValue({ edge_id: 1 } as never);
    deleteAlignmentMutationMock.mockResolvedValue({ success: true } as never);
    const selectedMeta = buildMeta("OBJECTIVE", 77);

    const { result } = renderHook(() =>
      useInspectorAuxData({
        user: baseUser,
        selectedMeta,
        rolloutAllowed: true,
        parsedCycleId: null,
        loadSnapshotForUser: vi.fn().mockResolvedValue(undefined),
      }),
    );

    await waitFor(() => expect(readBackendQueryMock).toHaveBeenCalledTimes(1));

    act(() => {
      result.current.setAlignmentDirection("child");
      result.current.setAlignmentTargetObjectiveId("91");
    });

    await act(async () => {
      await result.current.handleAlignmentCreate();
    });

    expect(createAlignmentMutationMock).toHaveBeenCalledWith({
      actor_username: "alice",
      parent_id: 77,
      child_id: 91,
      alignment_type: "SUPPORTS",
    });
    expect(result.current.alignmentTargetObjectiveId).toBe("");

    await act(async () => {
      await result.current.handleAlignmentDelete(123);
    });
    expect(deleteAlignmentMutationMock).toHaveBeenCalledWith({
      actor_username: "alice",
      edge_id: 123,
    });
    expect(readBackendQueryMock).toHaveBeenCalledTimes(3);
  });

  it("deletes task work log when confirmed and refreshes snapshot", async () => {
    const readBackendQueryMock = vi.mocked(api.readBackendQuery);
    const deleteWorkLogMutationMock = vi.mocked(api.deleteWorkLogMutation);
    const loadSnapshotForUser = vi.fn().mockResolvedValue(undefined);
    if (!("confirm" in window)) {
      Object.defineProperty(window, "confirm", {
        value: () => true,
        writable: true,
        configurable: true,
      });
    }
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);

    readBackendQueryMock.mockResolvedValue({
      work_logs: [{ id: 33, end_time: "2026-02-27T12:00:00Z", duration_minutes: 5 }],
    });
    deleteWorkLogMutationMock.mockResolvedValue({ success: true } as never);
    const selectedMeta = buildMeta("TASK", 88);

    const { result } = renderHook(() =>
      useInspectorAuxData({
        user: baseUser,
        selectedMeta,
        rolloutAllowed: true,
        parsedCycleId: 4,
        loadSnapshotForUser,
      }),
    );

    await waitFor(() => expect(readBackendQueryMock).toHaveBeenCalledTimes(1));

    await act(async () => {
      await result.current.handleInspectorDeleteWorkLog(33);
    });

    expect(confirmSpy).toHaveBeenCalled();
    expect(deleteWorkLogMutationMock).toHaveBeenCalledWith({
      actor_username: "alice",
      work_log_id: 33,
    });
    expect(result.current.inspectTaskWorkLogsActionMessage).toContain("Deleted work log #33.");
    expect(loadSnapshotForUser).toHaveBeenCalledWith(baseUser);
    expect(readBackendQueryMock).toHaveBeenCalledTimes(2);
    confirmSpy.mockRestore();
  });
});
