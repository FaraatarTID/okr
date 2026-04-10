import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "@/lib/api";
import type { AuthUser } from "@/lib/api/auth";
import useLeadershipInsights from "@/components/atlas-shell/useLeadershipInsights";

vi.mock("@/lib/api", () => ({
  analyzeTeamCoachAi: vi.fn(),
  readLeadershipMetrics: vi.fn(),
  readStrategyPulseAi: vi.fn(),
}));

const baseUser: AuthUser = {
  id: 1,
  username: "alice",
  display_name: "Alice",
  role: "admin",
};

function buildMetrics(overrides: Record<string, unknown> = {}) {
  return {
    total_krs: 10,
    at_risk_count: 2,
    hygiene_pct: 74,
    avg_confidence: 6.8,
    at_risk: [{ title: "KR Launch", reason: "Timeline slip" }],
    member_progress: [{ username: "alice", progress: 61 }],
    member_deadlines: [{ completed: 2, on_track: 4, at_risk: 1, overdue: 0 }],
    ...overrides,
  };
}

describe("useLeadershipInsights", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
  });

  it("loads leadership metrics and seeds dashboard baselines", async () => {
    const readLeadershipMetricsMock = vi.mocked(api.readLeadershipMetrics);
    readLeadershipMetricsMock.mockResolvedValue(buildMetrics() as never);

    const { result } = renderHook(() =>
      useLeadershipInsights({
        mode: "dashboard",
        user: baseUser,
        parsedCycleId: 7,
        cycleLabel: "Q1-2026",
      }),
    );

    await act(async () => {
      await result.current.loadLeadershipMetricsSnapshot(baseUser);
    });

    expect(readLeadershipMetricsMock).toHaveBeenCalledWith({
      actor_username: "alice",
      cycle_id: 7,
    });
    await waitFor(() => expect(result.current.leadershipMetrics?.total_krs).toBe(10));
    await waitFor(() => expect(result.current.teamCoachSummary).not.toBeNull());
    await waitFor(() => expect(result.current.strategyPulseSummary).not.toBeNull());
  });

  it("falls back to baseline when team coach AI fails", async () => {
    const readLeadershipMetricsMock = vi.mocked(api.readLeadershipMetrics);
    const analyzeTeamCoachAiMock = vi.mocked(api.analyzeTeamCoachAi);
    readLeadershipMetricsMock.mockResolvedValue(buildMetrics() as never);
    analyzeTeamCoachAiMock.mockRejectedValue(new Error("team coach unavailable"));

    const { result } = renderHook(() =>
      useLeadershipInsights({
        mode: "dashboard",
        user: baseUser,
        parsedCycleId: 7,
        cycleLabel: "Q1-2026",
      }),
    );

    await act(async () => {
      await result.current.handleGenerateTeamCoachSummary();
    });

    expect(analyzeTeamCoachAiMock).toHaveBeenCalled();
    await waitFor(() =>
      expect(result.current.teamCoachError).toContain("showing baseline analysis"),
    );
    expect(result.current.teamCoachSummary).not.toBeNull();
  });

  it("merges strategy pulse AI data on top of baseline", async () => {
    const readLeadershipMetricsMock = vi.mocked(api.readLeadershipMetrics);
    const readStrategyPulseAiMock = vi.mocked(api.readStrategyPulseAi);
    readLeadershipMetricsMock.mockResolvedValue(buildMetrics() as never);
    readStrategyPulseAiMock.mockResolvedValue(
      {
        burnout_risk: "High",
        burnout_snapshot: {
          risk_score: 88,
          avg_daily_minutes: 57,
          completed_tasks: 6,
        },
        gap_signals: ["Deadlines bunching in week 4"],
        predictive_outlook: {
          outlook_summary: "Delivery pressure is rising.",
          confidence_level: 72,
          risk_mitigation: ["Reduce parallel WIP"],
          strategic_pivots: ["Split KR scope into two releases"],
        },
        portfolio_actions: ["Reorder team allocation by critical path"],
      } as never,
    );

    const { result } = renderHook(() =>
      useLeadershipInsights({
        mode: "dashboard",
        user: baseUser,
        parsedCycleId: 7,
        cycleLabel: "Q1-2026",
      }),
    );

    await act(async () => {
      await result.current.handleGenerateStrategyPulseSummary();
    });

    expect(readStrategyPulseAiMock).toHaveBeenCalledWith({
      actor_username: "alice",
      cycle_id: 7,
      cycle_title: "Q1-2026",
    });
    await waitFor(() =>
      expect(result.current.strategyPulseSummary?.burnoutRisk).toBe("High"),
    );
    expect(result.current.strategyPulseSummary?.confidenceLevel).toBe(72);
    expect(result.current.strategyPulseSummary?.mitigationSteps).toContain("Reduce parallel WIP");
  });

  it("clears team-coach and strategy-pulse views when mode leaves dashboard", async () => {
    const readLeadershipMetricsMock = vi.mocked(api.readLeadershipMetrics);
    readLeadershipMetricsMock.mockResolvedValue(buildMetrics() as never);

    const { result, rerender } = renderHook(
      (props: { mode: string }) =>
        useLeadershipInsights({
          mode: props.mode,
          user: baseUser,
          parsedCycleId: 7,
          cycleLabel: "Q1-2026",
        }),
      { initialProps: { mode: "dashboard" } },
    );

    await act(async () => {
      await result.current.loadLeadershipMetricsSnapshot(baseUser);
    });
    await waitFor(() => expect(result.current.teamCoachSummary).not.toBeNull());
    await waitFor(() => expect(result.current.strategyPulseSummary).not.toBeNull());

    rerender({ mode: "timeline" });

    await waitFor(() => expect(result.current.teamCoachSummary).toBeNull());
    await waitFor(() => expect(result.current.strategyPulseSummary).toBeNull());
    expect(result.current.teamCoachError).toBe("");
    expect(result.current.strategyPulseError).toBe("");
  });
});
