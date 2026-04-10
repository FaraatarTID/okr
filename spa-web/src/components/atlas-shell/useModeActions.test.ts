import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "@/lib/api";
import type { AuthUser } from "@/lib/api";
import useModeActions from "@/components/atlas-shell/useModeActions";

vi.mock("@/lib/api", () => ({
  createRetrospectiveMutation: vi.fn(),
  createWeeklyPlanMutation: vi.fn(),
}));

const baseUser: AuthUser = {
  id: 42,
  username: "alice",
  display_name: "Alice",
  role: "member",
};

function renderModeActionsHook(params?: {
  weeklyDraft?: { p1: string; p2: string; p3: string };
  retroDraft?: { content: string; sentiment: string };
  parsedCycleId?: number | null;
}) {
  const loadModeData = vi.fn().mockResolvedValue(undefined);
  const weeklyDraft = params?.weeklyDraft || { p1: "Ship auth hardening", p2: "", p3: "" };
  const hook = renderHook(() =>
    useModeActions({
      user: baseUser,
      parsedCycleId: params?.parsedCycleId ?? 7,
      weeklyDraft,
      retroDraft: params?.retroDraft || { content: "Solid week", sentiment: "positive" },
      setRetroDraft: vi.fn(),
      loadModeData,
      startOfWeekIso: () => "2026-02-23",
      endOfWeekIso: () => "2026-03-01",
      toIsoStart: (value) => `${value}T00:00:00Z`,
      toIsoEnd: (value) => `${value}T23:59:59Z`,
    }),
  );
  return {
    ...hook,
    loadModeData,
  };
}

describe("useModeActions", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
  });

  it("validates Priority 1 before saving weekly plan", async () => {
    const createWeeklyPlanMutationMock = vi.mocked(api.createWeeklyPlanMutation);
    const { result } = renderModeActionsHook({ weeklyDraft: { p1: "   ", p2: "", p3: "" } });

    await act(async () => {
      await result.current.handleWeeklyPlanSave();
    });

    expect(createWeeklyPlanMutationMock).not.toHaveBeenCalled();
    expect(result.current.modeActionError).toBe("Priority 1 is required.");
    expect(result.current.modeActionMessage).toBe("");
  });

  it("saves weekly plan and refreshes weekly mode data", async () => {
    const createWeeklyPlanMutationMock = vi.mocked(api.createWeeklyPlanMutation);
    createWeeklyPlanMutationMock.mockResolvedValue({ id: 1 } as never);
    const { result, loadModeData } = renderModeActionsHook({
      weeklyDraft: { p1: "Launch SPA-first CI", p2: "Fix e2e", p3: "" },
    });

    await act(async () => {
      await result.current.handleWeeklyPlanSave();
    });

    expect(createWeeklyPlanMutationMock).toHaveBeenCalledWith(
      expect.objectContaining({
        actor_username: "alice",
        p1: "Launch SPA-first CI",
      }),
    );
    expect(loadModeData).toHaveBeenCalledWith(baseUser, "weekly");
    expect(result.current.modeActionMessage).toBe("Weekly priorities saved.");
    expect(result.current.modeActionError).toBe("");
  });

  it("validates retrospective content before create", async () => {
    const createRetrospectiveMutationMock = vi.mocked(api.createRetrospectiveMutation);
    const { result } = renderModeActionsHook({ retroDraft: { content: "   ", sentiment: "" } });

    await act(async () => {
      await result.current.handleRetroCreate();
    });

    expect(createRetrospectiveMutationMock).not.toHaveBeenCalled();
    expect(result.current.modeActionError).toBe("Retrospective content is required.");
    expect(result.current.modeActionMessage).toBe("");
  });

  it("creates retrospective and refreshes ritual mode data", async () => {
    const createRetrospectiveMutationMock = vi.mocked(api.createRetrospectiveMutation);
    createRetrospectiveMutationMock.mockResolvedValue({ id: 9 } as never);
    const setRetroDraft = vi.fn();
    const loadModeData = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() =>
      useModeActions({
        user: baseUser,
        parsedCycleId: 9,
        weeklyDraft: { p1: "p1", p2: "", p3: "" },
        retroDraft: { content: "Closed key risks", sentiment: "relieved" },
        setRetroDraft,
        loadModeData,
        startOfWeekIso: () => "2026-02-23",
        endOfWeekIso: () => "2026-03-01",
        toIsoStart: (value) => `${value}T00:00:00Z`,
        toIsoEnd: (value) => `${value}T23:59:59Z`,
      }),
    );

    await act(async () => {
      await result.current.handleRetroCreate("ritual", "2026-02-23");
    });

    expect(createRetrospectiveMutationMock).toHaveBeenCalledWith(
      expect.objectContaining({
        actor_username: "alice",
        cycle_id: 9,
        week_start_date: "2026-02-23T00:00:00Z",
      }),
    );
    expect(setRetroDraft).toHaveBeenCalledWith({ content: "", sentiment: "" });
    expect(loadModeData).toHaveBeenCalledWith(baseUser, "ritual");
    expect(result.current.modeActionMessage).toBe("Retrospective added.");
  });
});
