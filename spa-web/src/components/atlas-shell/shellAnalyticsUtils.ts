import type { LeadershipMetricsResponse } from "@/lib/api";

export type WorkLogLike = {
  task_id?: number | null;
  duration_minutes?: number | null;
  task?: { title?: string | null } | null;
};

export type AnalysisSummaryView = {
  efficiencyScore: number | null;
  effectivenessScore: number | null;
  overallScore: number | null;
  summary: string;
  gapAnalysis: string;
  qualityAssessment: string;
  deadlineWarnings: string[];
  proposedTasks: string[];
  raw: Record<string, unknown> | null;
};

export type ReportAiSummaryView = {
  summaryMarkdown: string;
  highlights: string[];
  focusAnalysis: string;
};

export type TeamCoachSummaryView = {
  healthScore: number | null;
  healthGrade: string;
  topPriorities: string[];
  quickWins: string[];
  watchOuts: string[];
  dimensionNotes: string[];
};

export type StrategyPulseSummaryView = {
  burnoutRisk: string;
  burnoutScore: number | null;
  avgDailyMinutes: number | null;
  completedTasks14d: number | null;
  gapSignals: string[];
  predictiveOutlook: string;
  confidenceLevel: number | null;
  mitigationSteps: string[];
  strategicPivots: string[];
  portfolioActions: string[];
};

export function clampProgress(value: unknown): number {
  const raw = Number(value);
  if (!Number.isFinite(raw)) {
    return 0;
  }
  const rounded = Math.round(raw);
  if (rounded < 0) {
    return 0;
  }
  if (rounded > 100) {
    return 100;
  }
  return rounded;
}

export function sumLogMinutes(logs: WorkLogLike[]): number {
  return Math.round(
    logs.reduce((sum, item) => sum + Number(item.duration_minutes || 0), 0),
  );
}

export function averageLogMinutes(logs: WorkLogLike[]): number {
  if (!logs.length) {
    return 0;
  }
  return Math.round(sumLogMinutes(logs) / logs.length);
}

export function groupLogsByTask(logs: WorkLogLike[]): Array<{
  taskId: number | null;
  title: string;
  minutes: number;
  sessions: number;
}> {
  const aggregate = new Map<string, { taskId: number | null; title: string; minutes: number; sessions: number }>();
  for (const log of logs) {
    const rawTaskId = Number(log.task_id);
    const taskId = Number.isFinite(rawTaskId) && rawTaskId > 0 ? rawTaskId : null;
    const title = String(log.task?.title || (taskId ? `Task #${taskId}` : "Unknown task"));
    const key = `${taskId || "none"}:${title}`;
    const row = aggregate.get(key) || { taskId, title, minutes: 0, sessions: 0 };
    row.minutes += Number(log.duration_minutes || 0);
    row.sessions += 1;
    aggregate.set(key, row);
  }
  return [...aggregate.values()]
    .map((row) => ({ ...row, minutes: Math.round(row.minutes) }))
    .sort((left, right) => right.minutes - left.minutes);
}

export function formatSignedDelta(value: number): string {
  const rounded = Math.round(Number(value || 0));
  if (rounded > 0) {
    return `+${rounded}`;
  }
  return `${rounded}`;
}

export function aiProgressDecision(
  currentProgress: unknown,
  aiScore: unknown,
  maxDelta: number,
  allowDecrease: boolean,
): {
  action: "apply" | "skip";
  reason: "within_policy" | "missing_ai_score" | "no_change" | "decrease_blocked" | "delta_cap";
  current: number;
  proposed: number | null;
  delta: number | null;
} {
  const current = clampProgress(currentProgress);
  const parsedAi = Number(aiScore);
  if (!Number.isFinite(parsedAi)) {
    return { action: "skip", reason: "missing_ai_score", current, proposed: null, delta: null };
  }
  const proposed = clampProgress(parsedAi);
  const delta = proposed - current;
  const boundedDelta = clampProgress(maxDelta);
  if (delta === 0) {
    return { action: "skip", reason: "no_change", current, proposed, delta };
  }
  if (delta < 0 && !allowDecrease) {
    return { action: "skip", reason: "decrease_blocked", current, proposed, delta };
  }
  if (Math.abs(delta) > boundedDelta) {
    return { action: "skip", reason: "delta_cap", current, proposed, delta };
  }
  return { action: "apply", reason: "within_policy", current, proposed, delta };
}

const ANALYSIS_STALE_MS = 24 * 60 * 60 * 1000;

export function isAnalysisStale(
  analysisUpdatedAt: string | null | undefined,
): boolean {
  if (!analysisUpdatedAt) return true;
  const updated = new Date(analysisUpdatedAt).getTime();
  if (!Number.isFinite(updated)) return true;
  return Date.now() - updated > ANALYSIS_STALE_MS;
}

export function parseNumberOrNull(value: unknown): number | null {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

export function parseAnalysisSummary(raw: unknown): AnalysisSummaryView {
  let payload: Record<string, unknown> | null = null;
  if (raw && typeof raw === "object") {
    payload = raw as Record<string, unknown>;
  } else if (typeof raw === "string" && raw.trim()) {
    try {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === "object") {
        payload = parsed as Record<string, unknown>;
      }
    } catch {
      payload = null;
    }
  }
  const warnings = Array.isArray(payload?.deadline_warnings)
    ? payload?.deadline_warnings.map((item) => String(item || "").trim()).filter(Boolean)
    : [];
  const proposed = Array.isArray(payload?.proposed_tasks)
    ? payload?.proposed_tasks
        .map((item) => {
          if (typeof item === "string") {
            return String(item || "").trim();
          }
          if (!item || typeof item !== "object") {
            return "";
          }
          const row = item as Record<string, unknown>;
          return String(row.title || row.task || row.name || "").trim();
        })
        .filter(Boolean)
    : [];
  return {
    efficiencyScore: parseNumberOrNull(payload?.efficiency_score),
    effectivenessScore: parseNumberOrNull(payload?.effectiveness_score),
    overallScore: parseNumberOrNull(payload?.overall_score),
    summary: String(payload?.summary || "").trim(),
    gapAnalysis: String(payload?.gap_analysis || "").trim(),
    qualityAssessment: String(payload?.quality_assessment || "").trim(),
    deadlineWarnings: warnings,
    proposedTasks: proposed,
    raw: payload,
  };
}

export function parseReportAiSummary(raw: unknown): ReportAiSummaryView {
  const payload =
    raw && typeof raw === "object" ? (raw as Record<string, unknown>) : ({} as Record<string, unknown>);
  const highlights = Array.isArray(payload.highlights)
    ? payload.highlights.map((row) => String(row || "").trim()).filter(Boolean)
    : [];
  return {
    summaryMarkdown: String(payload.summary_markdown || "").trim(),
    highlights,
    focusAnalysis: String(payload.focus_analysis || "").trim(),
  };
}

export function parseStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => String(item || "").trim()).filter(Boolean);
}

export function parseTeamCoachSummary(raw: unknown): TeamCoachSummaryView {
  const payload =
    raw && typeof raw === "object" ? (raw as Record<string, unknown>) : ({} as Record<string, unknown>);
  return {
    healthScore: parseNumberOrNull(payload.health_score),
    healthGrade: String(payload.health_grade || "").trim(),
    topPriorities: parseStringArray(payload.top_priorities),
    quickWins: parseStringArray(payload.quick_wins),
    watchOuts: parseStringArray(payload.watch_outs),
    dimensionNotes: parseStringArray(payload.dimension_notes),
  };
}

export function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

export function parseTeamCoachFromCoachingPayload(raw: unknown): TeamCoachSummaryView | null {
  const payload = asRecord(raw);
  const coaching = asRecord(payload?.coaching);
  if (!coaching) {
    return null;
  }
  const dimensions = asRecord(coaching.dimensions) || {};
  const dimensionNotes: string[] = [];
  for (const [key, value] of Object.entries(dimensions)) {
    const row = asRecord(value);
    if (!row) {
      continue;
    }
    const insight = String(row.insight || "").trim();
    const action = String(row.action || "").trim();
    const status = String(row.status || "").trim();
    const label = key.replace(/_/g, " ");
    const text = `${label}: ${status}${insight ? ` | ${insight}` : ""}${action ? ` | action: ${action}` : ""}`;
    if (text.trim()) {
      dimensionNotes.push(text.trim());
    }
  }
  const watchOut = String(coaching.watch_out || "").trim();
  return {
    healthScore: parseNumberOrNull(coaching.overall_health_score),
    healthGrade: String(coaching.health_grade || "").trim(),
    topPriorities: parseStringArray(coaching.top_priorities),
    quickWins: parseStringArray(coaching.quick_wins),
    watchOuts: watchOut ? [watchOut] : [],
    dimensionNotes,
  };
}

export function parseStrategyPulseSummary(raw: unknown): StrategyPulseSummaryView {
  const payload = asRecord(raw) || ({} as Record<string, unknown>);
  const burnout = asRecord(payload.burnout_snapshot);
  const outlook = asRecord(payload.predictive_outlook);
  const strategyGaps = Array.isArray(payload.strategy_gaps)
    ? payload.strategy_gaps
        .map((row) => asRecord(row))
        .filter((row): row is Record<string, unknown> => Boolean(row))
    : [];
  const gapSignalsFromRows = strategyGaps
    .slice(0, 5)
    .map((gap) => {
      const title = String(gap.title || "Untitled").trim();
      const gapType = String(gap.gap_type || "N/A").trim();
      const severity = Number(gap.severity || 0);
      return `${title}: ${gapType} (severity ${Math.round(severity)})`;
    })
    .filter(Boolean);
  const mitigationSteps = parseStringArray(outlook?.risk_mitigation);
  const strategicPivots = parseStringArray(outlook?.strategic_pivots);
  const portfolioActions = parseStringArray(payload.portfolio_actions);
  const confidenceLevel = parseNumberOrNull(outlook?.confidence_level);
  return {
    burnoutRisk: String(payload.burnout_risk || burnout?.risk_label || "").trim(),
    burnoutScore: parseNumberOrNull(burnout?.risk_score),
    avgDailyMinutes: parseNumberOrNull(burnout?.avg_daily_minutes),
    completedTasks14d: parseNumberOrNull(burnout?.completed_tasks),
    gapSignals: parseStringArray(payload.gap_signals).length
      ? parseStringArray(payload.gap_signals)
      : gapSignalsFromRows,
    predictiveOutlook: String(payload.predictive_outlook || outlook?.outlook_summary || "").trim(),
    confidenceLevel,
    mitigationSteps,
    strategicPivots,
    portfolioActions: portfolioActions.length ? portfolioActions : [...mitigationSteps, ...strategicPivots],
  };
}

export function buildTeamCoachBaseline(metrics: LeadershipMetricsResponse | null): TeamCoachSummaryView {
  const hygiene = Math.max(0, Math.min(100, Number(metrics?.hygiene_pct || 0)));
  const avgConfidence10 = Math.max(0, Math.min(10, Number(metrics?.avg_confidence || 0)));
  const totalKrs = Math.max(0, Number(metrics?.total_krs || 0));
  const atRiskCount = Math.max(0, Number(metrics?.at_risk_count || 0));
  const riskRatio = totalKrs > 0 ? atRiskCount / totalKrs : 0;
  const riskScore = 100 - Math.round(riskRatio * 100);
  const confidenceScore = Math.round(avgConfidence10 * 10);
  const healthScore = Math.max(
    0,
    Math.min(100, Math.round(hygiene * 0.35 + confidenceScore * 0.25 + riskScore * 0.4)),
  );
  const healthGrade = healthScore >= 85 ? "A" : healthScore >= 70 ? "B" : healthScore >= 55 ? "C" : healthScore >= 40 ? "D" : "F";

  const topPriorities: string[] = [];
  if (atRiskCount > 0) {
    topPriorities.push(`Recover ${atRiskCount} at-risk key results with focused owner interventions.`);
  }
  if (hygiene < 70) {
    topPriorities.push("Improve weekly check-in hygiene to stabilize decision quality.");
  }
  if (avgConfidence10 < 5) {
    topPriorities.push("Raise confidence through tighter KR evidence and coaching cadence.");
  }
  if (!topPriorities.length) {
    topPriorities.push("Maintain current execution cadence and guard against regression.");
  }

  const quickWins: string[] = [];
  if (hygiene < 85) {
    quickWins.push("Run a 30-minute check-in completion sweep for stale KRs.");
  }
  if (avgConfidence10 < 7) {
    quickWins.push("Require concise evidence notes on each check-in update.");
  }
  if (!quickWins.length) {
    quickWins.push("Promote top-performing playbooks across team members.");
  }

  const atRiskRows = Array.isArray(metrics?.at_risk) ? metrics?.at_risk : [];
  const watchOuts = atRiskRows
    .slice(0, 3)
    .map((row) => String((row as Record<string, unknown>).reason || "").trim())
    .filter(Boolean);

  const dimensionNotes = [
    `Productivity signal: ${(Array.isArray(metrics?.member_progress) ? metrics?.member_progress.length : 0)} members tracked.`,
    `Deadline discipline: ${atRiskCount}/${Math.max(totalKrs, 1)} KRs at risk.`,
    `Strategic alignment: hygiene ${Math.round(hygiene)}%, confidence ${avgConfidence10.toFixed(1)}/10.`,
  ];

  return {
    healthScore,
    healthGrade,
    topPriorities,
    quickWins,
    watchOuts,
    dimensionNotes,
  };
}

export function buildStrategyPulseBaseline(metrics: LeadershipMetricsResponse | null): StrategyPulseSummaryView {
  const avgConfidence10 = Math.max(0, Math.min(10, Number(metrics?.avg_confidence || 0)));
  const hygiene = Math.max(0, Math.min(100, Number(metrics?.hygiene_pct || 0)));
  const totalKrs = Math.max(0, Number(metrics?.total_krs || 0));
  const atRiskCount = Math.max(0, Number(metrics?.at_risk_count || 0));
  const riskRatio = totalKrs > 0 ? atRiskCount / totalKrs : 0;

  let burnoutRisk = "Healthy";
  if (riskRatio > 0.45 || avgConfidence10 < 4) {
    burnoutRisk = "Critical";
  } else if (riskRatio > 0.3 || avgConfidence10 < 5) {
    burnoutRisk = "High";
  } else if (riskRatio > 0.15 || avgConfidence10 < 6.5) {
    burnoutRisk = "Elevated";
  }

  const atRiskRows = Array.isArray(metrics?.at_risk) ? metrics?.at_risk : [];
  const gapSignals = atRiskRows
    .slice(0, 5)
    .map((row) => {
      const item = row as Record<string, unknown>;
      return `${String(item.title || "KR").trim()}: ${String(item.reason || "Needs review").trim()}`;
    })
    .filter(Boolean);

  const predictiveOutlook =
    burnoutRisk === "Healthy"
      ? "Current trajectory is stable if check-in hygiene remains consistent."
      : burnoutRisk === "Elevated"
        ? "Trajectory is mixed; prioritize short-cycle risk mitigation on exposed KRs."
        : burnoutRisk === "High"
          ? "Delivery risk is rising; rebalance workload and narrow active commitments."
          : "Critical delivery pressure detected; immediate scope triage is required.";

  const portfolioActions = [
    hygiene < 75 ? "Increase evidence-backed check-ins to improve portfolio traceability." : "Preserve high-quality evidence flow for completed outcomes.",
    atRiskCount > 0 ? "Package recovered at-risk KR turnarounds as leadership case studies." : "Promote completed KR patterns as repeatable strategic playbooks.",
  ];

  return {
    burnoutRisk,
    burnoutScore: Math.round(riskRatio * 100),
    avgDailyMinutes: null,
    completedTasks14d: null,
    gapSignals,
    predictiveOutlook,
    confidenceLevel: null,
    mitigationSteps: [],
    strategicPivots: [],
    portfolioActions,
  };
}
