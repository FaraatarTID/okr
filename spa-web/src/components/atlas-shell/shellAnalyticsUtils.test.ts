import { describe, expect, it } from "vitest";

import {
  aiProgressDecision,
  asRecord,
  averageLogMinutes,
  buildStrategyPulseBaseline,
  buildTeamCoachBaseline,
  clampProgress,
  formatSignedDelta,
  groupLogsByTask,
  parseAnalysisSummary,
  parseReportAiSummary,
  parseStrategyPulseSummary,
  parseTeamCoachFromCoachingPayload,
  parseTeamCoachSummary,
  sumLogMinutes,
} from "@/components/atlas-shell/shellAnalyticsUtils";

describe("shellAnalyticsUtils", () => {
  it("clamps progress to integer 0..100", () => {
    expect(clampProgress(-20)).toBe(0);
    expect(clampProgress(49.6)).toBe(50);
    expect(clampProgress(120)).toBe(100);
    expect(clampProgress("bad")).toBe(0);
  });

  it("aggregates work logs", () => {
    const logs = [
      { task_id: 7, duration_minutes: 12.4, task: { title: "Auth" } },
      { task_id: 7, duration_minutes: 18.6, task: { title: "Auth" } },
      { task_id: 9, duration_minutes: 20, task: { title: "Tests" } },
    ];

    expect(sumLogMinutes(logs)).toBe(51);
    expect(averageLogMinutes(logs)).toBe(17);

    const grouped = groupLogsByTask(logs);
    expect(grouped).toHaveLength(2);
    expect(grouped[0]).toEqual({ taskId: 7, title: "Auth", minutes: 31, sessions: 2 });
  });

  it("formats deltas and policy decisions", () => {
    expect(formatSignedDelta(5.4)).toBe("+5");
    expect(formatSignedDelta(-1.2)).toBe("-1");

    expect(aiProgressDecision(20, 30, 20, false)).toMatchObject({ action: "apply", delta: 10 });
    expect(aiProgressDecision(20, 20, 20, false)).toMatchObject({ action: "skip", reason: "no_change" });
    expect(aiProgressDecision(50, 10, 20, false)).toMatchObject({ action: "skip", reason: "decrease_blocked" });
    expect(aiProgressDecision(10, 90, 30, true)).toMatchObject({ action: "skip", reason: "delta_cap" });
    expect(aiProgressDecision(10, "x", 30, true)).toMatchObject({ action: "skip", reason: "missing_ai_score" });
  });

  it("parses analysis and report summaries", () => {
    const analysis = parseAnalysisSummary({
      efficiency_score: 76,
      effectiveness_score: 71,
      overall_score: 73,
      summary: "Stable trend",
      proposed_tasks: ["Tighten triage", { title: "Reduce queue depth" }],
      deadline_warnings: ["KR-2 overdue"],
    });
    expect(analysis.overallScore).toBe(73);
    expect(analysis.proposedTasks).toEqual(["Tighten triage", "Reduce queue depth"]);

    const analysisFromString = parseAnalysisSummary(
      JSON.stringify({ summary: "From string", proposed_tasks: [{ task: "One more check" }] }),
    );
    expect(analysisFromString.summary).toBe("From string");
    expect(analysisFromString.proposedTasks).toEqual(["One more check"]);

    const report = parseReportAiSummary({
      summary_markdown: "Weekly view",
      highlights: ["A", "B"],
      focus_analysis: "Focus up",
    });
    expect(report.highlights).toEqual(["A", "B"]);
    expect(report.focusAnalysis).toBe("Focus up");
  });

  it("parses team coach payloads", () => {
    const direct = parseTeamCoachSummary({
      health_score: 88,
      health_grade: "A",
      top_priorities: ["Priority 1"],
      quick_wins: ["Win 1"],
      watch_outs: ["Watch 1"],
      dimension_notes: ["Note 1"],
    });
    expect(direct.healthScore).toBe(88);
    expect(direct.topPriorities).toEqual(["Priority 1"]);

    const fromCoaching = parseTeamCoachFromCoachingPayload({
      coaching: {
        overall_health_score: 72,
        health_grade: "B",
        top_priorities: ["Rebalance queue"],
        quick_wins: ["Close stale tasks"],
        watch_out: "Burnout risk in squad A",
        dimensions: {
          execution: { status: "amber", insight: "variability", action: "tighten WIP" },
        },
      },
    });
    expect(fromCoaching?.healthGrade).toBe("B");
    expect(fromCoaching?.watchOuts).toEqual(["Burnout risk in squad A"]);
    expect(fromCoaching?.dimensionNotes[0]).toContain("execution");
    expect(parseTeamCoachFromCoachingPayload({})).toBeNull();
  });

  it("parses strategy pulse payload and fallback signals", () => {
    const parsed = parseStrategyPulseSummary({
      burnout_risk: "Elevated",
      burnout_snapshot: { risk_score: 64, avg_daily_minutes: 83, completed_tasks: 14 },
      predictive_outlook: {
        outlook_summary: "Watchlist",
        confidence_level: 62,
        risk_mitigation: ["Mitigate"],
        strategic_pivots: ["Pivot A"],
      },
      strategy_gaps: [{ title: "KR-A", gap_type: "alignment", severity: 52 }],
    });

    expect(parsed.burnoutRisk).toBe("Elevated");
    expect(parsed.burnoutScore).toBe(64);
    expect(parsed.gapSignals[0]).toContain("KR-A");
    expect(parsed.portfolioActions).toEqual(["Mitigate", "Pivot A"]);
  });

  it("builds deterministic baselines", () => {
    const coach = buildTeamCoachBaseline({
      hygiene_pct: 64,
      avg_confidence: 5.2,
      at_risk_count: 3,
      total_krs: 10,
      at_risk: [{ reason: "missed check-ins" }],
      member_progress: [{ user: "a" }, { user: "b" }],
    });
    expect(coach.healthScore).not.toBeNull();
    expect(coach.topPriorities.length).toBeGreaterThan(0);
    expect(coach.watchOuts).toEqual(["missed check-ins"]);

    const strategy = buildStrategyPulseBaseline({
      hygiene_pct: 55,
      avg_confidence: 4.4,
      at_risk_count: 5,
      total_krs: 10,
      at_risk: [{ title: "KR-1", reason: "slipping" }],
    });
    expect(strategy.burnoutRisk).toBe("Critical");
    expect(strategy.burnoutScore).toBe(50);
    expect(strategy.gapSignals[0]).toContain("KR-1");
  });

  it("guards record coercion", () => {
    expect(asRecord(null)).toBeNull();
    expect(asRecord([])).toBeNull();
    expect(asRecord({ ok: true })).toEqual({ ok: true });
  });
});
