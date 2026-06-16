import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "@/lib/api";
import type { AuthUser } from "@/lib/api/auth";
import useRitualActions from "@/components/atlas-shell/useRitualActions";

vi.mock("@/lib/api", () => ({
  createCheckInMutation: vi.fn(),
  closeExperimentMutation: vi.fn(),
  createExperimentMutation: vi.fn(),
  updateExperimentMutation: vi.fn(),
}));

const baseUser: AuthUser = {
  id: 1,
  username: "alice",
  display_name: "Alice",
  role: "admin",
};

type RitualExperiment = {
  id: number;
  key_result_id: number;
  cycle_id: number;
  status?: "PLANNED" | "RUNNING" | "DECIDED" | null;
};

function renderRitualHook(options?: {
  parsedCycleId?: number | null;
  ritualKrs?: Array<{ id: number; progress?: number | null; current_value?: number | null }>;
  ritualExperimentsByKr?: Record<number, RitualExperiment[]>;
}) {
  const loadModeData = vi.fn().mockResolvedValue(undefined);
  const loadSnapshotForUser = vi.fn().mockResolvedValue(undefined);
  const appendRitualExperiment = vi.fn();
  const ritualKrs = options?.ritualKrs ?? [{ id: 1, progress: 25, current_value: 30 }];
  const ritualExperimentsByKr = options?.ritualExperimentsByKr ?? {};

  const hook = renderHook(() =>
    useRitualActions({
      user: baseUser,
      parsedCycleId: options?.parsedCycleId ?? 7,
      ritualKrs,
      ritualExperimentsByKr,
      loadModeData,
      loadSnapshotForUser,
      appendRitualExperiment,
    }),
  );

  return {
    ...hook,
    loadModeData,
    loadSnapshotForUser,
    appendRitualExperiment,
  };
}

describe("useRitualActions", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
  });

  it("initializes check-in drafts from ritual KR payload", async () => {
    const { result } = renderRitualHook({
      ritualKrs: [{ id: 10, current_value: 42, progress: 30 }],
    });

    await waitFor(() => expect(result.current.ritualCheckInDrafts[10]?.value).toBe("42"));
    expect(result.current.ritualCheckInDrafts[10]?.confidence).toBe("CONFIDENT");
    expect(result.current.ritualCheckInDrafts[10]?.variationType).toBe("COMMON_CAUSE");
  });

  it("creates experiment and appends it into ritual experiment map", async () => {
    const createExperimentMutationMock = vi.mocked(api.createExperimentMutation);
    const { result, appendRitualExperiment } = renderRitualHook();

    createExperimentMutationMock.mockResolvedValue({
      id: 88,
      key_result_id: 1,
      cycle_id: 7,
      status: "PLANNED",
      hypothesis: "Focus on scope limits",
      change_description: "Trim WIP",
    } as never);

    act(() => {
      result.current.updateRitualExperimentDraft(1, {
        hypothesis: "Focus on scope limits",
        changeDescription: "Trim WIP",
      });
    });

    await act(async () => {
      await result.current.handleRitualExperimentCreate({ id: 1 });
    });

    expect(createExperimentMutationMock).toHaveBeenCalledWith(
      expect.objectContaining({
        actor_username: "alice",
        key_result_id: 1,
        cycle_id: 7,
      }),
    );
    expect(appendRitualExperiment).toHaveBeenCalledWith(
      1,
      expect.objectContaining({
        id: 88,
        key_result_id: 1,
      }),
    );
    expect(result.current.ritualExperimentMessage[1]).toContain("Experiment created as PLANNED");
  });

  it("rejects low-confidence check-ins without comment", async () => {
    const createCheckInMutationMock = vi.mocked(api.createCheckInMutation);
    const { result } = renderRitualHook();

    act(() => {
      result.current.updateRitualCheckInDraft(1, {
        value: "25",
        confidence: "UNCERTAIN",
        comment: "",
      });
    });

    await act(async () => {
      await result.current.handleRitualCheckInSubmit({ id: 1 });
    });

    expect(createCheckInMutationMock).not.toHaveBeenCalled();
    expect(result.current.ritualCheckInError[1]).toContain("Uncertain check-ins require a comment");
  });

  it("submits check-in with running experiment link and refreshes ritual mode", async () => {
    const createCheckInMutationMock = vi.mocked(api.createCheckInMutation);
    createCheckInMutationMock.mockResolvedValue({ id: 5 } as never);

    const { result, loadModeData, loadSnapshotForUser } = renderRitualHook({
      ritualExperimentsByKr: {
        1: [{ id: 9, key_result_id: 1, cycle_id: 7, status: "RUNNING" }],
      },
    });

    act(() => {
      result.current.updateRitualCheckInDraft(1, {
        value: "45",
        confidence: "CONFIDENT",
        comment: "On-track",
        variationType: "COMMON_CAUSE",
        experimentId: "9",
      });
    });

    await act(async () => {
      await result.current.handleRitualCheckInSubmit({ id: 1 });
    });

    expect(createCheckInMutationMock).toHaveBeenCalledWith(
      expect.objectContaining({
        actor_username: "alice",
        kr_id: 1,
        experiment_id: 9,
      }),
    );
    expect(loadModeData).toHaveBeenCalledWith(baseUser, "ritual");
    expect(loadSnapshotForUser).toHaveBeenCalledWith(baseUser);
    expect(result.current.ritualCheckInMessage[1]).toBe("Check-in saved.");
  });

  it("starts ritual experiment and blocks close without rationale", async () => {
    const updateExperimentMutationMock = vi.mocked(api.updateExperimentMutation);
    const closeExperimentMutationMock = vi.mocked(api.closeExperimentMutation);
    updateExperimentMutationMock.mockResolvedValue({ id: 20 } as never);
    closeExperimentMutationMock.mockResolvedValue({ id: 20 } as never);

    const { result, loadModeData, loadSnapshotForUser } = renderRitualHook();

    await act(async () => {
      await result.current.handleRitualExperimentStart(20);
    });

    expect(updateExperimentMutationMock).toHaveBeenCalledWith(
      expect.objectContaining({
        actor_username: "alice",
        experiment_id: 20,
        updates: expect.objectContaining({ status: "RUNNING" }),
      }),
    );
    expect(loadModeData).toHaveBeenCalledWith(baseUser, "ritual");
    expect(loadSnapshotForUser).toHaveBeenCalledWith(baseUser);

    await act(async () => {
      await result.current.handleRitualExperimentClose(20);
    });

    expect(closeExperimentMutationMock).not.toHaveBeenCalled();
    expect(result.current.ritualExperimentActionError[20]).toContain("Decision rationale is required.");
  });
});
