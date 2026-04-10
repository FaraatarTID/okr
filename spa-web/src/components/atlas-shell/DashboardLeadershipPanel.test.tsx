import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import DashboardLeadershipPanel from "@/components/atlas-shell/DashboardLeadershipPanel";

describe("DashboardLeadershipPanel", () => {
  it("does not render for users without leadership access", () => {
    render(
      <DashboardLeadershipPanel
        canViewLeadership={false}
        leadershipPending={false}
        teamCoachPending={false}
        strategyPulsePending={false}
        parsedCycleId={1}
        leadershipError=""
        teamCoachError=""
        strategyPulseError=""
        leadershipMetrics={null}
        teamCoachSummary={null}
        strategyPulseSummary={null}
        onRefreshMetrics={vi.fn()}
        onGenerateTeamCoach={vi.fn()}
        onGenerateStrategyPulse={vi.fn()}
      />,
    );

    expect(screen.queryByRole("heading", { name: "Leadership Insights" })).not.toBeInTheDocument();
  });

  it("renders summaries and triggers all actions when enabled", async () => {
    const user = userEvent.setup();
    const onRefreshMetrics = vi.fn();
    const onGenerateTeamCoach = vi.fn();
    const onGenerateStrategyPulse = vi.fn();

    render(
      <DashboardLeadershipPanel
        canViewLeadership
        leadershipPending={false}
        teamCoachPending={false}
        strategyPulsePending={false}
        parsedCycleId={12}
        leadershipError=""
        teamCoachError=""
        strategyPulseError=""
        leadershipMetrics={{ hygiene_pct: 84.2, avg_confidence: 7.25 }}
        teamCoachSummary={{
          healthScore: 92,
          healthGrade: "A",
          topPriorities: ["Stabilize on-call", "Raise test confidence"],
          quickWins: ["Close stale incidents"],
          watchOuts: ["Latency variance"],
        }}
        strategyPulseSummary={{
          burnoutRisk: "moderate",
          burnoutScore: 43,
          avgDailyMinutes: 78,
          completedTasks14d: 19,
          gapSignals: ["handoff risk"],
          predictiveOutlook: "on-track with watch",
          confidenceLevel: 71,
        }}
        onRefreshMetrics={onRefreshMetrics}
        onGenerateTeamCoach={onGenerateTeamCoach}
        onGenerateStrategyPulse={onGenerateStrategyPulse}
      />,
    );

    expect(screen.getByText("84%")).toBeInTheDocument();
    expect(screen.getByText("7.3/10")).toBeInTheDocument();
    expect(screen.getByText(/Priorities: Stabilize on-call \| Raise test confidence/i)).toBeInTheDocument();
    expect(screen.getByText(/Quick wins: Close stale incidents/i)).toBeInTheDocument();
    expect(screen.getByText(/Watch-outs: Latency variance/i)).toBeInTheDocument();
    expect(screen.getByText(/Burnout risk: moderate \(43\/100\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Avg daily focus: 78m \| 14d output: 19 tasks/i)).toBeInTheDocument();
    expect(screen.getByText(/Outlook: on-track with watch \(confidence 71%\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Gap signals: handoff risk/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Refresh Metrics" }));
    await user.click(screen.getByRole("button", { name: "Generate Team Coach" }));
    await user.click(screen.getByRole("button", { name: "Generate Strategy Pulse" }));

    expect(onRefreshMetrics).toHaveBeenCalledTimes(1);
    expect(onGenerateTeamCoach).toHaveBeenCalledTimes(1);
    expect(onGenerateStrategyPulse).toHaveBeenCalledTimes(1);
  });

  it("shows errors and disables actions when cycle is missing or requests are pending", () => {
    render(
      <DashboardLeadershipPanel
        canViewLeadership
        leadershipPending
        teamCoachPending
        strategyPulsePending
        parsedCycleId={null}
        leadershipError="metrics failed"
        teamCoachError="coach failed"
        strategyPulseError="pulse failed"
        leadershipMetrics={null}
        teamCoachSummary={null}
        strategyPulseSummary={null}
        onRefreshMetrics={vi.fn()}
        onGenerateTeamCoach={vi.fn()}
        onGenerateStrategyPulse={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Loading..." })).toBeDisabled();
    expect(screen.getAllByRole("button", { name: "Generating..." })).toHaveLength(2);
    expect(screen.getByText("metrics failed")).toBeInTheDocument();
    expect(screen.getByText("coach failed")).toBeInTheDocument();
    expect(screen.getByText("pulse failed")).toBeInTheDocument();
  });
});
