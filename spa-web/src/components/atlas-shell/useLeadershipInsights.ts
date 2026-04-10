"use client";

import { useCallback, useEffect, useState } from "react";

import {
  analyzeTeamCoachAi,
  readLeadershipMetrics,
  readStrategyPulseAi,
  type AuthUser,
  type LeadershipMetricsResponse,
} from "@/lib/api";
import {
  buildStrategyPulseBaseline,
  buildTeamCoachBaseline,
  parseStrategyPulseSummary,
  parseTeamCoachFromCoachingPayload,
  parseTeamCoachSummary,
  type StrategyPulseSummaryView,
  type TeamCoachSummaryView,
} from "@/components/atlas-shell/shellAnalyticsUtils";

type UseLeadershipInsightsInput = {
  mode: string;
  user: AuthUser | null;
  parsedCycleId: number | null;
  cycleLabel: string;
};

export default function useLeadershipInsights({
  mode,
  user,
  parsedCycleId,
  cycleLabel,
}: UseLeadershipInsightsInput) {
  const [leadershipMetrics, setLeadershipMetrics] = useState<LeadershipMetricsResponse | null>(null);
  const [leadershipPending, setLeadershipPending] = useState(false);
  const [leadershipError, setLeadershipError] = useState("");
  const [teamCoachPending, setTeamCoachPending] = useState(false);
  const [teamCoachError, setTeamCoachError] = useState("");
  const [teamCoachSummary, setTeamCoachSummary] = useState<TeamCoachSummaryView | null>(null);
  const [strategyPulsePending, setStrategyPulsePending] = useState(false);
  const [strategyPulseError, setStrategyPulseError] = useState("");
  const [strategyPulseSummary, setStrategyPulseSummary] = useState<StrategyPulseSummaryView | null>(null);

  useEffect(() => {
    if (mode !== "dashboard") {
      setTeamCoachSummary(null);
      setTeamCoachError("");
      setStrategyPulseSummary(null);
      setStrategyPulseError("");
    }
  }, [mode]);

  useEffect(() => {
    if (mode !== "dashboard" || !leadershipMetrics) {
      return;
    }
    setTeamCoachSummary((prev) => prev || buildTeamCoachBaseline(leadershipMetrics));
    setStrategyPulseSummary((prev) => prev || buildStrategyPulseBaseline(leadershipMetrics));
  }, [leadershipMetrics, mode]);

  const loadLeadershipMetricsSnapshot = useCallback(
    async (activeUser: AuthUser): Promise<LeadershipMetricsResponse | null> => {
      if (!parsedCycleId) {
        setLeadershipMetrics(null);
        return null;
      }
      setLeadershipPending(true);
      setLeadershipError("");
      try {
        const metrics = await readLeadershipMetrics({
          actor_username: activeUser.username,
          cycle_id: parsedCycleId,
        });
        setLeadershipMetrics(metrics || null);
        return metrics || null;
      } catch (error) {
        setLeadershipError(String(error instanceof Error ? error.message : error));
        setLeadershipMetrics(null);
        return null;
      } finally {
        setLeadershipPending(false);
      }
    },
    [parsedCycleId],
  );

  const handleGenerateTeamCoachSummary = useCallback(async (): Promise<void> => {
    if (!user || !parsedCycleId) {
      return;
    }
    const metrics = leadershipMetrics || (await loadLeadershipMetricsSnapshot(user)) || {};
    setTeamCoachPending(true);
    setTeamCoachError("");
    const baseline = buildTeamCoachBaseline(metrics);
    setTeamCoachSummary(baseline);
    try {
      const memberProgressData = Array.isArray(metrics.member_progress)
        ? metrics.member_progress
        : [];
      const memberDeadlineData = Array.isArray(metrics.member_deadlines)
        ? metrics.member_deadlines
        : [];
      const deadlineAggregate = memberDeadlineData.reduce<{
        completed: number;
        on_track: number;
        at_risk: number;
        overdue: number;
      }>(
        (acc, row) => {
          const item = (row || {}) as Record<string, unknown>;
          acc.completed += Number(item.completed || 0);
          acc.on_track += Number(item.on_track || 0);
          acc.at_risk += Number(item.at_risk || 0);
          acc.overdue += Number(item.overdue || 0);
          return acc;
        },
        { completed: 0, on_track: 0, at_risk: 0, overdue: 0 },
      );
      const teamData = {
        members: memberProgressData,
        total_with_deadline:
          deadlineAggregate.completed +
          deadlineAggregate.on_track +
          deadlineAggregate.at_risk +
          deadlineAggregate.overdue,
        completed: deadlineAggregate.completed,
        on_track: deadlineAggregate.on_track,
        at_risk: deadlineAggregate.at_risk,
        overdue: deadlineAggregate.overdue,
        total_krs: Number(metrics.total_krs || 0),
        at_risk_krs: Array.isArray(metrics.at_risk) ? metrics.at_risk.length : 0,
        avg_confidence: Number(metrics.avg_confidence || 0),
        hygiene_pct: Number(metrics.hygiene_pct || 0),
        progress_distribution: memberProgressData,
      };
      const aiPayload = await analyzeTeamCoachAi({
        actor_username: user.username,
        team_data: teamData,
      });
      const ai =
        parseTeamCoachFromCoachingPayload(aiPayload) || parseTeamCoachSummary(aiPayload);
      if (!ai.healthGrade && ai.healthScore === null && !ai.topPriorities.length) {
        throw new Error("AI team coach returned empty payload.");
      }
      setTeamCoachSummary({
        healthScore: ai.healthScore ?? baseline.healthScore,
        healthGrade: ai.healthGrade || baseline.healthGrade,
        topPriorities: ai.topPriorities.length ? ai.topPriorities : baseline.topPriorities,
        quickWins: ai.quickWins.length ? ai.quickWins : baseline.quickWins,
        watchOuts: ai.watchOuts.length ? ai.watchOuts : baseline.watchOuts,
        dimensionNotes: ai.dimensionNotes.length ? ai.dimensionNotes : baseline.dimensionNotes,
      });
    } catch (error) {
      setTeamCoachError(`${String(error instanceof Error ? error.message : error)} (showing baseline analysis).`);
    } finally {
      setTeamCoachPending(false);
    }
  }, [leadershipMetrics, loadLeadershipMetricsSnapshot, parsedCycleId, user]);

  const handleGenerateStrategyPulseSummary = useCallback(async (): Promise<void> => {
    if (!user || !parsedCycleId) {
      return;
    }
    const metrics = leadershipMetrics || (await loadLeadershipMetricsSnapshot(user)) || {};
    setStrategyPulsePending(true);
    setStrategyPulseError("");
    const baseline = buildStrategyPulseBaseline(metrics);
    setStrategyPulseSummary(baseline);
    try {
      const aiPayload = await readStrategyPulseAi({
        actor_username: user.username,
        cycle_id: parsedCycleId,
        cycle_title: cycleLabel,
      });
      const ai = parseStrategyPulseSummary(aiPayload || {});
      setStrategyPulseSummary({
        burnoutRisk: ai.burnoutRisk || baseline.burnoutRisk,
        burnoutScore: ai.burnoutScore ?? baseline.burnoutScore,
        avgDailyMinutes: ai.avgDailyMinutes ?? baseline.avgDailyMinutes,
        completedTasks14d: ai.completedTasks14d ?? baseline.completedTasks14d,
        gapSignals: ai.gapSignals.length ? ai.gapSignals : baseline.gapSignals,
        predictiveOutlook: ai.predictiveOutlook || baseline.predictiveOutlook,
        confidenceLevel: ai.confidenceLevel ?? baseline.confidenceLevel,
        mitigationSteps: ai.mitigationSteps.length ? ai.mitigationSteps : baseline.mitigationSteps,
        strategicPivots: ai.strategicPivots.length ? ai.strategicPivots : baseline.strategicPivots,
        portfolioActions: ai.portfolioActions.length ? ai.portfolioActions : baseline.portfolioActions,
      });
    } catch (error) {
      setStrategyPulseError(`${String(error instanceof Error ? error.message : error)} (showing baseline analysis).`);
    } finally {
      setStrategyPulsePending(false);
    }
  }, [cycleLabel, leadershipMetrics, loadLeadershipMetricsSnapshot, parsedCycleId, user]);

  return {
    leadershipMetrics,
    leadershipPending,
    leadershipError,
    teamCoachPending,
    teamCoachError,
    teamCoachSummary,
    strategyPulsePending,
    strategyPulseError,
    strategyPulseSummary,
    loadLeadershipMetricsSnapshot,
    handleGenerateTeamCoachSummary,
    handleGenerateStrategyPulseSummary,
  };
}
