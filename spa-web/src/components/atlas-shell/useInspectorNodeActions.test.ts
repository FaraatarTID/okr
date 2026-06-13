import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "@/lib/api";
import type { AuthUser } from "@/lib/api/auth";
import type { AtlasIndexNode, AtlasNodeType } from "@/lib/atlas";
import useInspectorNodeActions from "@/components/atlas-shell/useInspectorNodeActions";

vi.mock("@/lib/api", () => ({
  analyzeNodeAi: vi.fn(),
  createNodeMutation: vi.fn(),
  deleteNodeMutation: vi.fn(),
  updateNodeMutation: vi.fn(),
}));

const baseUser: AuthUser = {
  id: 1,
  username: "alice",
  display_name: "Alice",
  role: "admin",
};

function buildSelectedMeta(nodeType: AtlasNodeType, id: number): AtlasIndexNode {
  const ref = nodeType === "KEY_RESULT" ? `key_result_${id}` : `${nodeType.toLowerCase()}_${id}`;
  const base = {
    id,
    title: `${nodeType} ${id}`,
    description: `${nodeType} description`,
    progress: 35,
  };
  const node =
    nodeType === "GOAL"
      ? { ...base, owner_id: 1, objectives: [] }
      : nodeType === "OBJECTIVE"
        ? { ...base, key_results: [] }
        : nodeType === "KEY_RESULT"
          ? { ...base, gemini_analysis: null, tasks: [] }
          : {
              ...base,
              deadline: null,
              timer_started_at: null,
              status: "TODO",
              total_time_spent: 0,
              assignee_id: 1,
            };

  return {
    ref,
    id,
    node: node as AtlasIndexNode["node"],
    type: nodeType,
    title: base.title,
    titleLower: base.title.toLowerCase(),
    description: base.description,
    progress: base.progress,
    depth: 0,
    parent: null,
    path: [ref],
    children: [],
    ownerId: 1,
    nodeOwnerId: 1,
    timerOwnerId: 1,
    ownerName: "Alice",
  };
}

describe("useInspectorNodeActions", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
  });

  it("runs analysis, persists payload, and refreshes snapshot", async () => {
    const analyzeNodeAiMock = vi.mocked(api.analyzeNodeAi);
    const updateNodeMutationMock = vi.mocked(api.updateNodeMutation);
    const loadSnapshotForUser = vi.fn().mockResolvedValue(undefined);
    const setSelectedRef = vi.fn();
    const setFocusTaskRef = vi.fn();
    const selectedMeta = buildSelectedMeta("KEY_RESULT", 12);

    analyzeNodeAiMock.mockResolvedValue({
      overall_score: 87,
      summary: "Strong momentum",
    } as never);
    updateNodeMutationMock.mockResolvedValue({} as never);

    const { result } = renderHook(() =>
      useInspectorNodeActions({
        user: baseUser,
        selectedMeta,

        parsedCycleId: 7,
        createContext: { goalId: 1, objectiveId: 2, keyResultId: 3 },
        focusTaskRef: "",
        loadSnapshotForUser,
        setSelectedRef,
        setFocusTaskRef,
      }),
    );

    await act(async () => {
      await result.current.handleInspectorRunAnalysis();
    });

    expect(analyzeNodeAiMock).toHaveBeenCalledWith({
      actor_username: "alice",
      node_id: 12,
      node_type: "KEY_RESULT",
    });
    expect(updateNodeMutationMock).toHaveBeenCalledWith({
      actor_username: "alice",
      node_type: "key_result",
      node_id: 12,
      updates: {
        gemini_analysis: expect.objectContaining({
          overall_score: 87,
        }),
      },
    });
    expect(loadSnapshotForUser).toHaveBeenCalledWith(baseUser);
    await waitFor(() => expect(result.current.inspectAnalysis?.overallScore).toBe(87));
    expect(result.current.inspectMessage).toContain("AI analysis refreshed");
  });

  it("blocks save when progress is outside 0-100 range", async () => {
    const updateNodeMutationMock = vi.mocked(api.updateNodeMutation);
    const loadSnapshotForUser = vi.fn().mockResolvedValue(undefined);
    const setSelectedRef = vi.fn();
    const setFocusTaskRef = vi.fn();
    const selectedMeta = buildSelectedMeta("OBJECTIVE", 21);

    const { result } = renderHook(() =>
      useInspectorNodeActions({
        user: baseUser,
        selectedMeta,

        parsedCycleId: 7,
        createContext: { goalId: 10, objectiveId: 20, keyResultId: 30 },
        focusTaskRef: "",
        loadSnapshotForUser,
        setSelectedRef,
        setFocusTaskRef,
      }),
    );

    act(() => {
      result.current.setInspectDraft((prev) => ({ ...prev, progress: "101" }));
    });

    await act(async () => {
      await result.current.handleInspectorSave();
    });

    expect(updateNodeMutationMock).not.toHaveBeenCalled();
    expect(result.current.inspectError).toContain("Progress must be an integer between 0 and 100.");
  });

  it("creates node and selects created reference", async () => {
    const createNodeMutationMock = vi.mocked(api.createNodeMutation);
    const loadSnapshotForUser = vi.fn().mockResolvedValue(undefined);
    const setSelectedRef = vi.fn();
    const setFocusTaskRef = vi.fn();
    const selectedMeta = buildSelectedMeta("GOAL", 10);

    createNodeMutationMock.mockResolvedValue({
      id: 77,
      node_type: "OBJECTIVE",
    } as never);

    const { result } = renderHook(() =>
      useInspectorNodeActions({
        user: baseUser,
        selectedMeta,

        parsedCycleId: 7,
        createContext: { goalId: 10, objectiveId: 20, keyResultId: 30 },
        focusTaskRef: "",
        loadSnapshotForUser,
        setSelectedRef,
        setFocusTaskRef,
      }),
    );

    act(() => {
      result.current.setCreateDraft((prev) => ({
        ...prev,
        title: "Stabilize auth boundary",
        description: "Lock down actor derivation",
      }));
    });

    await act(async () => {
      await result.current.handleNodeCreate();
    });

    expect(createNodeMutationMock).toHaveBeenCalledWith({
      actor_username: "alice",
      create_type: "objective",
      payload: expect.objectContaining({
        title: "Stabilize auth boundary",
        description: "Lock down actor derivation",
        goal_id: 10,
      }),
    });
    expect(setSelectedRef).toHaveBeenCalledWith("objective_77");
    expect(loadSnapshotForUser).toHaveBeenCalledWith(baseUser);
    expect(result.current.createMessage).toContain("Created Objective #77.");
  });

  it("defaults to goal creation when no node is selected", async () => {
    const createNodeMutationMock = vi.mocked(api.createNodeMutation);
    const loadSnapshotForUser = vi.fn().mockResolvedValue(undefined);
    const setSelectedRef = vi.fn();
    const setFocusTaskRef = vi.fn();

    createNodeMutationMock.mockResolvedValue({
      id: 15,
      node_type: "GOAL",
    } as never);

    const { result } = renderHook(() =>
      useInspectorNodeActions({
        user: baseUser,
        selectedMeta: null,

        parsedCycleId: 7,
        createContext: { goalId: null, objectiveId: null, keyResultId: null },
        focusTaskRef: "",
        loadSnapshotForUser,
        setSelectedRef,
        setFocusTaskRef,
      }),
    );

    expect(result.current.createDraft.createType).toBe("goal");
    expect(result.current.canCreateForContext).toBe(true);

    act(() => {
      result.current.setCreateDraft((prev) => ({
        ...prev,
        title: "Launch operating cadence",
        description: "Seed first program goal",
      }));
    });

    await act(async () => {
      await result.current.handleNodeCreate();
    });

    expect(createNodeMutationMock).toHaveBeenCalledWith({
      actor_username: "alice",
      create_type: "goal",
      payload: expect.objectContaining({
        user_id: "alice",
        title: "Launch operating cadence",
        description: "Seed first program goal",
        cycle_id: 7,
      }),
    });
    expect(setSelectedRef).toHaveBeenCalledWith("goal_15");
    expect(loadSnapshotForUser).toHaveBeenCalledWith(baseUser);
  });

  it("deletes selected task and clears focus when confirmed", async () => {
    const deleteNodeMutationMock = vi.mocked(api.deleteNodeMutation);
    const loadSnapshotForUser = vi.fn().mockResolvedValue(undefined);
    const setSelectedRef = vi.fn();
    const setFocusTaskRef = vi.fn();
    const selectedMeta = buildSelectedMeta("TASK", 31);
    const confirmMock = vi.fn().mockReturnValue(true);
    Object.defineProperty(window, "confirm", {
      value: confirmMock,
      configurable: true,
      writable: true,
    });

    deleteNodeMutationMock.mockResolvedValue({} as never);

    const { result } = renderHook(() =>
      useInspectorNodeActions({
        user: baseUser,
        selectedMeta,

        parsedCycleId: 7,
        createContext: { goalId: 10, objectiveId: 20, keyResultId: 30 },
        focusTaskRef: selectedMeta.ref,
        loadSnapshotForUser,
        setSelectedRef,
        setFocusTaskRef,
      }),
    );

    await act(async () => {
      await result.current.handleNodeDelete();
    });

    expect(confirmMock).toHaveBeenCalled();
    expect(deleteNodeMutationMock).toHaveBeenCalledWith({
      actor_username: "alice",
      node_type: "task",
      node_id: 31,
    });
    expect(setSelectedRef).toHaveBeenCalledWith("");
    expect(setFocusTaskRef).toHaveBeenCalledWith("");
    expect(loadSnapshotForUser).toHaveBeenCalledWith(baseUser);
    expect(result.current.deleteMessage).toContain("Deleted Task #31.");
  });
});
