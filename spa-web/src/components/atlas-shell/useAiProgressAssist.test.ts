import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "@/lib/api";
import type { AuthUser } from "@/lib/api/auth";
import type { AtlasIndexNode, AtlasKeyResultSnapshot, AtlasTaskSnapshot } from "@/lib/atlas";
import * as jobPolling from "@/components/atlas-shell/jobPolling";
import useAiProgressAssist from "@/components/atlas-shell/useAiProgressAssist";

vi.mock("@/lib/api", () => ({
  submitBackendJob: vi.fn(),
  updateNodeMutation: vi.fn(),
}));

vi.mock("@/components/atlas-shell/jobPolling", () => ({
  waitForBackendJobResult: vi.fn(),
}));

const baseUser: AuthUser = {
  id: 1,
  username: "alice",
  display_name: "Alice",
  role: "admin",
};

function buildKeyResultNode(
  id: number,
  title: string,
  progress: number,
  aiOverallScore: number | null,
): AtlasIndexNode {
  return {
    ref: `key_result_${id}`,
    id,
    node: {
      id,
      title,
      description: "",
      progress,
      ai_overall_score: aiOverallScore,
      tasks: [],
    } as AtlasKeyResultSnapshot,
    type: "KEY_RESULT",
    title,
    titleLower: title.toLowerCase(),
    description: "",
    progress,
    depth: 0,
    parent: null,
    path: [`key_result_${id}`],
    children: [],
    ownerId: 1,
    nodeOwnerId: 1,
    timerOwnerId: 1,
    ownerName: "Alice",
  };
}

function buildTaskNode(id: number, parentRef: string, title = `Task ${id}`): AtlasIndexNode {
  return {
    ref: `task_${id}`,
    id,
    node: {
      id,
      title,
      description: "",
      progress: 15,
      deadline: null,
      timer_started_at: null,
      status: "TODO",
      total_time_spent: 0,
      assignee_id: 1,
    } as AtlasTaskSnapshot,
    type: "TASK",
    title,
    titleLower: title.toLowerCase(),
    description: "",
    progress: 15,
    depth: 1,
    parent: parentRef,
    path: [parentRef, `task_${id}`],
    children: [],
    ownerId: 1,
    nodeOwnerId: 1,
    timerOwnerId: 1,
    ownerName: "Alice",
  };
}

describe("useAiProgressAssist", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
  });

  it("previews KR sync without mutating progress", async () => {
    const updateNodeMutationMock = vi.mocked(api.updateNodeMutation);
    const loadSnapshotForUser = vi.fn().mockResolvedValue(undefined);
    const onTaskSuggested = vi.fn();
    const kr = buildKeyResultNode(1, "KR 1", 20, 60);

    const { result } = renderHook(() =>
      useAiProgressAssist({
        user: baseUser,

        parsedCycleId: 7,
        atlasRuntime: { index: { [kr.ref]: kr } },
        allScopeRefs: [kr.ref],
        taskRefs: [],
        aiSyncMaxDelta: 40,
        aiSyncAllowDecrease: false,
        loadSnapshotForUser,
        onTaskSuggested,
      }),
    );

    await act(async () => {
      await result.current.handleAiProgressSync(true);
    });

    expect(updateNodeMutationMock).not.toHaveBeenCalled();
    expect(result.current.aiSyncReport?.planned).toBe(1);
    expect(result.current.aiSyncReport?.applied).toBe(0);
    expect(result.current.aiSyncMessage).toContain("Preview");
    expect(loadSnapshotForUser).not.toHaveBeenCalled();
  });

  it("applies sync and supports undo of applied KR updates", async () => {
    const updateNodeMutationMock = vi.mocked(api.updateNodeMutation);
    const loadSnapshotForUser = vi.fn().mockResolvedValue(undefined);
    const onTaskSuggested = vi.fn();
    const kr = buildKeyResultNode(2, "KR 2", 20, 60);
    updateNodeMutationMock.mockResolvedValue({} as never);

    const { result } = renderHook(() =>
      useAiProgressAssist({
        user: baseUser,

        parsedCycleId: 7,
        atlasRuntime: { index: { [kr.ref]: kr } },
        allScopeRefs: [kr.ref],
        taskRefs: [],
        aiSyncMaxDelta: 40,
        aiSyncAllowDecrease: false,
        loadSnapshotForUser,
        onTaskSuggested,
      }),
    );

    await act(async () => {
      await result.current.handleAiProgressSync(false);
    });

    expect(updateNodeMutationMock).toHaveBeenCalledWith({
      actor_username: "alice",
      node_type: "key_result",
      node_id: 2,
      updates: { progress: 60 },
    });
    expect(result.current.aiProgressUndoItems).toHaveLength(1);
    expect(loadSnapshotForUser).toHaveBeenCalledWith(baseUser);

    updateNodeMutationMock.mockClear();

    await act(async () => {
      await result.current.handleAiProgressUndo();
    });

    expect(updateNodeMutationMock).toHaveBeenCalledWith({
      actor_username: "alice",
      node_type: "key_result",
      node_id: 2,
      updates: { progress: 20 },
    });
    expect(result.current.aiProgressUndoItems).toHaveLength(0);
    expect(result.current.aiSyncMessage).toContain("Undo complete");
  });

  it("suggests next task and emits task-selection callback", async () => {
    const submitBackendJobMock = vi.mocked(api.submitBackendJob);
    const waitForBackendJobResultMock = vi.mocked(jobPolling.waitForBackendJobResult);
    const loadSnapshotForUser = vi.fn().mockResolvedValue(undefined);
    const onTaskSuggested = vi.fn();
    const kr = buildKeyResultNode(3, "KR 3", 10, 65);
    const task = buildTaskNode(10, kr.ref, "Draft rollout checklist");

    submitBackendJobMock.mockResolvedValue({ id: "job-suggest-1" } as never);
    waitForBackendJobResultMock.mockResolvedValue({
      status: "SUCCEEDED",
      result: {
        task_ref: task.ref,
        reason: "High urgency and high impact",
        confidence: 88,
      },
    } as never);

    const { result } = renderHook(() =>
      useAiProgressAssist({
        user: baseUser,

        parsedCycleId: 7,
        atlasRuntime: {
          index: {
            [kr.ref]: kr,
            [task.ref]: task,
          },
        },
        allScopeRefs: [kr.ref, task.ref],
        taskRefs: [task.ref],
        aiSyncMaxDelta: 40,
        aiSyncAllowDecrease: false,
        loadSnapshotForUser,
        onTaskSuggested,
      }),
    );

    await act(async () => {
      await result.current.handleAiSuggestNextTask();
    });

    expect(submitBackendJobMock).toHaveBeenCalledWith(
      expect.objectContaining({
        actor_username: "alice",
        kind: "ai.generate_json",
      }),
    );
    expect(waitForBackendJobResultMock).toHaveBeenCalledWith(baseUser, "job-suggest-1");
    await waitFor(() => expect(result.current.aiSuggestion?.taskRef).toBe(task.ref));
    expect(onTaskSuggested).toHaveBeenCalledWith(task.ref);
    expect(result.current.aiSyncMessage).toContain("Suggested next task");
  });
});
