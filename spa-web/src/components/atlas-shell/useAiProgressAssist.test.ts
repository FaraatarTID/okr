import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "@/lib/api";
import type { AuthUser } from "@/lib/api/auth";
import type { AtlasIndexNode, AtlasKeyResultSnapshot, AtlasTaskSnapshot } from "@/lib/atlas";
import * as jobPolling from "@/components/atlas-shell/jobPolling";
import useAiProgressAssist from "@/components/atlas-shell/useAiProgressAssist";

vi.mock("@/lib/api", () => ({
  analyzeNodeAi: vi.fn(),
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
      analysis_updated_at: new Date().toISOString(),
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
      progress: 0,
      deadline: null,
      timer_started_at: null,
      status: "IN_PROGRESS",
      total_time_spent: 0,
      estimated_minutes: 30,
      assignee_id: null,
    } as AtlasTaskSnapshot,
    type: "TASK",
    title,
    titleLower: title.toLowerCase(),
    description: "",
    progress: 0,
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

  it("runs analysis without mutating progress", async () => {
    const loadSnapshotForUser = vi.fn().mockResolvedValue(undefined);
    const onTaskSuggested = vi.fn();
    const kr = buildKeyResultNode(1, "KR 1", 20, null);

    vi.mocked(api.analyzeNodeAi).mockResolvedValue({ overall_score: 65 } as never);
    vi.mocked(api.updateNodeMutation).mockResolvedValue({} as never);

    const { result } = renderHook(() =>
      useAiProgressAssist({
        user: baseUser,
        parsedCycleId: 7,
        atlasRuntime: { index: { [kr.ref]: kr } },
        allScopeRefs: [kr.ref],
        taskRefs: [],
        loadSnapshotForUser,
        onTaskSuggested,
      }),
    );

    await act(async () => {
      await result.current.handleAiProgressSync(false);
    });

    expect(result.current.aiSyncReport?.reanalyzed).toBe(1);
    expect(result.current.aiSyncMessage).toContain("Analysis complete");
    expect(loadSnapshotForUser).toHaveBeenCalled();
  });

  it("suggests next task and emits task-selection callback", async () => {
    const loadSnapshotForUser = vi.fn().mockResolvedValue(undefined);
    const onTaskSuggested = vi.fn();
    const task = buildTaskNode(10, "key_result_1", "Fix bug");
    const kr = buildKeyResultNode(1, "KR 1", 20, 60);

    vi.mocked(api.submitBackendJob).mockResolvedValue({ id: "job-1" } as never);
    vi.mocked(jobPolling.waitForBackendJobResult).mockResolvedValue({
      status: "succeeded",
      result: { task_ref: "task_10", reason: "High priority", confidence: 85 },
    } as never);

    const { result } = renderHook(() =>
      useAiProgressAssist({
        user: baseUser,
        parsedCycleId: 7,
        atlasRuntime: { index: { [kr.ref]: kr, [task.ref]: task } },
        allScopeRefs: [kr.ref],
        taskRefs: [task.ref],
        loadSnapshotForUser,
        onTaskSuggested,
      }),
    );

    await act(async () => {
      await result.current.handleAiSuggestNextTask();
    });

    expect(onTaskSuggested).toHaveBeenCalledWith("task_10");
    expect(result.current.aiSuggestion?.taskRef).toBe("task_10");
    expect(result.current.aiSyncMessage).toContain("Suggested next task");
  });
});
