"use client";

import type { LeadershipMetricsResponse } from "@/lib/api";

type TeamCoachSummaryView = {
  healthScore: number | null;
  healthGrade: string;
  topPriorities: string[];
  quickWins: string[];
  watchOuts: string[];
};

type StrategyPulseSummaryView = {
  burnoutRisk: string;
  burnoutScore: number | null;
  avgDailyMinutes: number | null;
  completedTasks14d: number | null;
  gapSignals: string[];
  predictiveOutlook: string;
  confidenceLevel: number | null;
};

type DashboardLeadershipPanelProps = {
  canViewLeadership: boolean;
  leadershipPending: boolean;
  teamCoachPending: boolean;
  strategyPulsePending: boolean;
  parsedCycleId: number | null;
  leadershipError: string;
  teamCoachError: string;
  strategyPulseError: string;
  leadershipMetrics: LeadershipMetricsResponse | null;
  teamCoachSummary: TeamCoachSummaryView | null;
  strategyPulseSummary: StrategyPulseSummaryView | null;
  onRefreshMetrics: () => void;
  onGenerateTeamCoach: () => void;
  onGenerateStrategyPulse: () => void;
};

export default function DashboardLeadershipPanel({
  canViewLeadership,
  leadershipPending,
  teamCoachPending,
  strategyPulsePending,
  parsedCycleId,
  leadershipError,
  teamCoachError,
  strategyPulseError,
  leadershipMetrics,
  teamCoachSummary,
  strategyPulseSummary,
  onRefreshMetrics,
  onGenerateTeamCoach,
  onGenerateStrategyPulse,
}: DashboardLeadershipPanelProps) {
  if (!canViewLeadership) {
    return null;
  }

  return (
    <div className="report-panel" style={{ marginTop: "0.55rem" }}>
      <div className="report-panel-head">
        <h3>Leadership Insights</h3>
        <div className="report-action-row">
          <button
            className="primary-button"
            type="button"
            onClick={onRefreshMetrics}
            disabled={leadershipPending || !parsedCycleId}
          >
            {leadershipPending ? "Loading..." : "Refresh Metrics"}
          </button>
          <button
            className="primary-button"
            type="button"
            onClick={onGenerateTeamCoach}
            disabled={teamCoachPending || leadershipPending || !parsedCycleId}
          >
            {teamCoachPending ? "Generating..." : "Generate Team Coach"}
          </button>
          <button
            className="primary-button"
            type="button"
            onClick={onGenerateStrategyPulse}
            disabled={strategyPulsePending || leadershipPending || !parsedCycleId}
          >
            {strategyPulsePending ? "Generating..." : "Generate Strategy Pulse"}
          </button>
        </div>
      </div>
      {leadershipError ? <p style={{ margin: "0.3rem 0 0", color: "var(--error)" }}>{leadershipError}</p> : null}
      {teamCoachError ? <p style={{ margin: "0.3rem 0 0", color: "var(--error)" }}>{teamCoachError}</p> : null}
      {strategyPulseError ? <p style={{ margin: "0.3rem 0 0", color: "var(--error)" }}>{strategyPulseError}</p> : null}

      <div className="report-card-grid" style={{ marginTop: "0.45rem" }}>
        {leadershipMetrics ? (
          <>
            <article className="report-metric-card">
              <p className="kicker" style={{ margin: 0 }}>Hygiene</p>
              <strong>{Math.round(Number(leadershipMetrics.hygiene_pct || 0))}%</strong>
              <span>Check-in + update consistency</span>
            </article>
            <article className="report-metric-card">
              <p className="kicker" style={{ margin: 0 }}>Average Confidence</p>
              <strong>{Number(leadershipMetrics.avg_confidence || 0).toFixed(1)}/10</strong>
              <span>Team-reported delivery confidence</span>
            </article>
          </>
        ) : null}
      </div>

      <div className="report-two-col" style={{ marginTop: "0.45rem" }}>
        {teamCoachSummary ? (
          <article className="report-panel accent">
            <div className="report-panel-head">
              <h4>Team Coach</h4>
              <span className="report-inline-score">
                {teamCoachSummary.healthGrade || "N/A"}
                {teamCoachSummary.healthScore !== null ? ` • ${Math.round(teamCoachSummary.healthScore)}%` : ""}
              </span>
            </div>
            {teamCoachSummary.topPriorities.length ? (
              <p className="report-inline-list">Priorities: {teamCoachSummary.topPriorities.join(" | ")}</p>
            ) : null}
            {teamCoachSummary.quickWins.length ? (
              <p className="report-inline-list">Quick wins: {teamCoachSummary.quickWins.join(" | ")}</p>
            ) : null}
            {teamCoachSummary.watchOuts.length ? (
              <p className="report-inline-list">Watch-outs: {teamCoachSummary.watchOuts.join(" | ")}</p>
            ) : null}
          </article>
        ) : null}

        {strategyPulseSummary ? (
          <article className="report-panel accent">
            <div className="report-panel-head">
              <h4>Strategy Pulse</h4>
            </div>
            {strategyPulseSummary.burnoutRisk ? (
              <p className="report-inline-list">
                Burnout risk: {strategyPulseSummary.burnoutRisk}
                {strategyPulseSummary.burnoutScore !== null
                  ? ` (${Math.round(strategyPulseSummary.burnoutScore)}/100)`
                  : ""}
              </p>
            ) : null}
            {(strategyPulseSummary.avgDailyMinutes !== null ||
              strategyPulseSummary.completedTasks14d !== null) ? (
                <p className="report-inline-list">
                  {strategyPulseSummary.avgDailyMinutes !== null
                    ? `Avg daily focus: ${Math.round(strategyPulseSummary.avgDailyMinutes)}m`
                    : ""}
                  {strategyPulseSummary.avgDailyMinutes !== null &&
                  strategyPulseSummary.completedTasks14d !== null
                    ? " | "
                    : ""}
                  {strategyPulseSummary.completedTasks14d !== null
                    ? `14d output: ${Math.round(strategyPulseSummary.completedTasks14d)} tasks`
                    : ""}
                </p>
              ) : null}
            {strategyPulseSummary.predictiveOutlook ? (
              <p className="report-inline-list">
                Outlook: {strategyPulseSummary.predictiveOutlook}
                {strategyPulseSummary.confidenceLevel !== null
                  ? ` (confidence ${Math.round(strategyPulseSummary.confidenceLevel)}%)`
                  : ""}
              </p>
            ) : null}
            {strategyPulseSummary.gapSignals.length ? (
              <p className="report-inline-list">Gap signals: {strategyPulseSummary.gapSignals.join(" | ")}</p>
            ) : null}
          </article>
        ) : null}
      </div>
    </div>
  );
}
