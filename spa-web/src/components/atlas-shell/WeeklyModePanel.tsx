"use client";

import type { Dispatch, SetStateAction } from "react";

type ReportAiSummaryView = {
  summaryMarkdown: string;
  highlights: string[];
  focusAnalysis: string;
} | null;

type WeeklyPlanDataView = {
  priority_1?: string | null;
  priority_2?: string | null;
  priority_3?: string | null;
} | null;

type WeeklyTopTaskView = {
  taskId: number | null;
  title: string;
  minutes: number;
  sessions: number;
};

type WeeklyKrView = {
  id: number;
  title?: string | null;
  progress?: number | null;
};

type WeeklyExperimentView = {
  id: number;
  status?: string | null;
  key_result_id: number;
};

type WeeklyDraftView = {
  p1: string;
  p2: string;
  p3: string;
};

type WeeklyModePanelProps = {
  weekRangeLabel: string;
  cycleLabel: string;
  reportExportPending: boolean;
  reportAiPending: boolean;
  reportExportError: string;
  reportAiError: string;
  onReportExport: (format: "pdf" | "html") => void;
  onGenerateAiSummary: () => void;
  weeklyTotalMinutes: number;
  weeklySessionCount: number;
  weeklyAverageMinutes: number;
  weeklyPriorityCoverage: { pct: number; filled: number; total: number };
  weeklyKrsNeedingCheckInCount: number;
  reportAiSummary: ReportAiSummaryView;
  weeklyPlanData: WeeklyPlanDataView;
  weeklyDraft: WeeklyDraftView;
  setWeeklyDraft: Dispatch<SetStateAction<WeeklyDraftView>>;
  onSaveWeeklyPlan: () => void;
  modeActionPending: boolean;
  weeklyTopTasks: WeeklyTopTaskView[];
  weeklyKrsNeedingCheckIn: WeeklyKrView[];
  weeklyReviewExperiments: WeeklyExperimentView[];
};

export default function WeeklyModePanel({
  weekRangeLabel,
  cycleLabel,
  reportExportPending,
  reportAiPending,
  reportExportError,
  reportAiError,
  onReportExport,
  onGenerateAiSummary,
  weeklyTotalMinutes,
  weeklySessionCount,
  weeklyAverageMinutes,
  weeklyPriorityCoverage,
  weeklyKrsNeedingCheckInCount,
  reportAiSummary,
  weeklyPlanData,
  weeklyDraft,
  setWeeklyDraft,
  onSaveWeeklyPlan,
  modeActionPending,
  weeklyTopTasks,
  weeklyKrsNeedingCheckIn,
  weeklyReviewExperiments,
}: WeeklyModePanelProps) {
  return (
    <>
      <div className="report-panel-head" style={{ marginTop: "0.35rem" }}>
        <div>
          <p className="kicker" style={{ margin: 0 }}>Weekly Report</p>
          <p style={{ margin: "0.2rem 0 0", color: "var(--ink-soft)" }}>
            {weekRangeLabel} • {cycleLabel}
          </p>
        </div>
        <div className="report-action-row">
          <button className="primary-button" type="button" onClick={() => onReportExport("pdf")} disabled={reportExportPending}>
            {reportExportPending ? "Exporting..." : "Export Weekly PDF"}
          </button>
          <button className="primary-button" type="button" onClick={() => onReportExport("html")} disabled={reportExportPending}>
            Export Weekly HTML
          </button>
          <button className="primary-button" type="button" onClick={onGenerateAiSummary} disabled={reportAiPending}>
            {reportAiPending ? "Generating..." : "Generate AI Summary"}
          </button>
        </div>
      </div>
      {reportExportError ? (
        <p style={{ margin: "0.3rem 0 0", color: "var(--error)" }}>{reportExportError}</p>
      ) : null}
      {reportAiError ? (
        <p style={{ margin: "0.3rem 0 0", color: "var(--error)" }}>{reportAiError}</p>
      ) : null}

      <div className="report-card-grid" style={{ marginTop: "0.45rem" }}>
        <article className="report-metric-card">
          <p className="kicker" style={{ margin: 0 }}>Focus Minutes</p>
          <strong>{weeklyTotalMinutes} min</strong>
          <span>{weeklySessionCount} sessions this week</span>
        </article>
        <article className="report-metric-card">
          <p className="kicker" style={{ margin: 0 }}>Average Session</p>
          <strong>{weeklyAverageMinutes} min</strong>
          <span>Per work-log block</span>
        </article>
        <article className="report-metric-card">
          <p className="kicker" style={{ margin: 0 }}>Priority Coverage</p>
          <strong>{weeklyPriorityCoverage.pct}%</strong>
          <div className="report-progress-track" aria-hidden="true">
            <span className="report-progress-fill" style={{ width: `${weeklyPriorityCoverage.pct}%` }} />
          </div>
          <span>
            {weeklyPriorityCoverage.filled}/{weeklyPriorityCoverage.total} weekly priorities set
          </span>
        </article>
        <article className="report-metric-card">
          <p className="kicker" style={{ margin: 0 }}>Check-In Backlog</p>
          <strong>{weeklyKrsNeedingCheckInCount}</strong>
          <span>KRs requiring check-in updates</span>
        </article>
      </div>

      {reportAiSummary ? (
        <section className="report-panel accent" style={{ marginTop: "0.5rem" }}>
          <div className="report-panel-head">
            <h3>AI Weekly Summary</h3>
          </div>
          {reportAiSummary.summaryMarkdown ? (
            <p style={{ margin: "0.24rem 0 0", whiteSpace: "pre-wrap" }}>{reportAiSummary.summaryMarkdown}</p>
          ) : null}
          {reportAiSummary.highlights.length ? (
            <ul style={{ margin: "0.28rem 0 0", paddingLeft: "1rem" }}>
              {reportAiSummary.highlights.map((item) => (
                <li key={item} style={{ margin: "0.15rem 0" }}>{item}</li>
              ))}
            </ul>
          ) : null}
          {reportAiSummary.focusAnalysis ? (
            <p className="report-inline-list">Focus analysis: {reportAiSummary.focusAnalysis}</p>
          ) : null}
        </section>
      ) : null}

      <div className="report-two-col" style={{ marginTop: "0.5rem" }}>
        <section className="report-panel">
          <div className="report-panel-head">
            <h3>Weekly Priorities</h3>
          </div>
          {weeklyPlanData ? (
            <div className="report-list" style={{ marginTop: "0.35rem" }}>
              <article className="report-list-row compact">
                <strong>Current plan</strong>
                <span>1. {weeklyPlanData.priority_1 || "-"}</span>
                <span>2. {weeklyPlanData.priority_2 || "-"}</span>
                <span>3. {weeklyPlanData.priority_3 || "-"}</span>
              </article>
            </div>
          ) : (
            <p className="report-empty" style={{ marginTop: "0.35rem" }}>
              No active weekly plan yet.
            </p>
          )}
          <div style={{ marginTop: "0.55rem", display: "grid", gap: "0.35rem" }}>
            <input className="input" value={weeklyDraft.p1} onChange={(event) => setWeeklyDraft((prev) => ({ ...prev, p1: event.target.value }))} placeholder="Priority 1 (required)" />
            <input className="input" value={weeklyDraft.p2} onChange={(event) => setWeeklyDraft((prev) => ({ ...prev, p2: event.target.value }))} placeholder="Priority 2" />
            <input className="input" value={weeklyDraft.p3} onChange={(event) => setWeeklyDraft((prev) => ({ ...prev, p3: event.target.value }))} placeholder="Priority 3" />
            <button className="primary-button" type="button" onClick={onSaveWeeklyPlan} disabled={modeActionPending}>
              {modeActionPending ? "Saving..." : "Save Weekly Priorities"}
            </button>
          </div>
        </section>

        <section className="report-panel">
          <div className="report-panel-head">
            <h3>Execution Signals</h3>
          </div>
          <div className="report-list" style={{ marginTop: "0.35rem" }}>
            <article className="report-list-row compact">
              <strong>Top Focus Tasks</strong>
              {weeklyTopTasks.length ? (
                weeklyTopTasks.map((row) => (
                  <span key={`${row.taskId || "none"}-${row.title}`}>
                    {row.title}: {row.minutes} min ({row.sessions} sessions)
                  </span>
                ))
              ) : (
                <span className="muted">No task-level focus logs this week.</span>
              )}
            </article>
            <article className="report-list-row compact">
              <strong>KRs Needing Check-In</strong>
              {weeklyKrsNeedingCheckIn.length ? (
                weeklyKrsNeedingCheckIn.slice(0, 6).map((kr) => (
                  <span key={kr.id}>
                    {kr.title || `KR #${kr.id}`} ({Math.round(Number(kr.progress || 0))}%)
                  </span>
                ))
              ) : (
                <span className="muted">No outstanding KR check-ins this week.</span>
              )}
            </article>
            <article className="report-list-row compact">
              <strong>Experiments in Review Window</strong>
              {weeklyReviewExperiments.length ? (
                weeklyReviewExperiments.slice(0, 6).map((exp) => (
                  <span key={exp.id}>
                    #{exp.id} • {String(exp.status || "PLANNED")} • KR #{exp.key_result_id}
                  </span>
                ))
              ) : (
                <span className="muted">No experiments recorded in this review window.</span>
              )}
            </article>
          </div>
        </section>
      </div>
    </>
  );
}
