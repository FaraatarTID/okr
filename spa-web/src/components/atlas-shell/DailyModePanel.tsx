"use client";

type ReportAiSummaryView = {
  summaryMarkdown: string;
  highlights: string[];
  focusAnalysis: string;
} | null;

type DailyTopTaskView = {
  taskId: number | null;
  title: string;
  minutes: number;
  sessions: number;
};

type DailyLogView = {
  id: number;
  task_id?: number | null;
  duration_minutes?: number | null;
  start_time?: string | null;
  summary?: string | null;
  task?: { title?: string | null } | null;
};

type DailyModePanelProps = {
  todayLabel: string;
  cycleLabel: string;
  reportExportPending: boolean;
  reportAiPending: boolean;
  reportExportError: string;
  reportAiError: string;
  onReportExport: (format: "pdf" | "html") => void;
  onGenerateAiSummary: () => void;
  dailyLogsFiltered: DailyLogView[];
  dailyTotalMinutes: number;
  dailyAverageMinutes: number;
  dailyDeepWorkShare: number;
  reportAiSummary: ReportAiSummaryView;
  dailyLogQuery: string;
  onDailyLogQueryChange: (value: string) => void;
  dailyTimeBands: { morning: number; afternoon: number; evening: number };
  dailyTopTasks: DailyTopTaskView[];
  formatOptionalDate: (value: unknown) => string;
};

export default function DailyModePanel({
  todayLabel,
  cycleLabel,
  reportExportPending,
  reportAiPending,
  reportExportError,
  reportAiError,
  onReportExport,
  onGenerateAiSummary,
  dailyLogsFiltered,
  dailyTotalMinutes,
  dailyAverageMinutes,
  dailyDeepWorkShare,
  reportAiSummary,
  dailyLogQuery,
  onDailyLogQueryChange,
  dailyTimeBands,
  dailyTopTasks,
  formatOptionalDate,
}: DailyModePanelProps) {
  return (
    <div style={{ marginTop: "0.35rem" }}>
      <div className="report-panel-head">
        <div>
          <p className="kicker" style={{ margin: 0 }}>Daily Report</p>
          <p style={{ margin: "0.2rem 0 0", color: "var(--ink-soft)" }}>
            {todayLabel} • {cycleLabel}
          </p>
        </div>
        <div className="report-action-row">
          <button className="primary-button" type="button" onClick={() => onReportExport("pdf")} disabled={reportExportPending}>
            {reportExportPending ? "Exporting..." : "Export Daily PDF"}
          </button>
          <button className="primary-button" type="button" onClick={() => onReportExport("html")} disabled={reportExportPending}>
            Export Daily HTML
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
          <p className="kicker" style={{ margin: 0 }}>Sessions</p>
          <strong>{dailyLogsFiltered.length}</strong>
          <span>Total work-log blocks (filtered)</span>
        </article>
        <article className="report-metric-card">
          <p className="kicker" style={{ margin: 0 }}>Focus Minutes</p>
          <strong>{dailyTotalMinutes}</strong>
          <span>Minutes tracked today</span>
        </article>
        <article className="report-metric-card">
          <p className="kicker" style={{ margin: 0 }}>Average Session</p>
          <strong>{dailyAverageMinutes} min</strong>
          <span>Per focus block</span>
        </article>
        <article className="report-metric-card">
          <p className="kicker" style={{ margin: 0 }}>Deep Work Share</p>
          <strong>{dailyDeepWorkShare}%</strong>
          <div className="report-progress-track" aria-hidden="true">
            <span className="report-progress-fill" style={{ width: `${dailyDeepWorkShare}%` }} />
          </div>
          <span>Share of sessions lasting 45+ minutes</span>
        </article>
      </div>

      {reportAiSummary ? (
        <section className="report-panel accent" style={{ marginTop: "0.5rem" }}>
          <div className="report-panel-head">
            <h3>AI Daily Summary</h3>
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
            <h3>Time Distribution</h3>
            <input
              className="input"
              value={dailyLogQuery}
              onChange={(event) => onDailyLogQueryChange(event.target.value)}
              placeholder="Filter by task, summary, or time"
              style={{ maxWidth: "17rem" }}
            />
          </div>
          <div className="band-row">
            <span>Morning</span>
            <div className="report-progress-track" aria-hidden="true">
              <span
                className="report-progress-fill"
                style={{
                  width: `${dailyTotalMinutes ? Math.round((dailyTimeBands.morning / dailyTotalMinutes) * 100) : 0}%`,
                }}
              />
            </div>
            <strong>{dailyTimeBands.morning}m</strong>
          </div>
          <div className="band-row">
            <span>Afternoon</span>
            <div className="report-progress-track" aria-hidden="true">
              <span
                className="report-progress-fill"
                style={{
                  width: `${dailyTotalMinutes ? Math.round((dailyTimeBands.afternoon / dailyTotalMinutes) * 100) : 0}%`,
                }}
              />
            </div>
            <strong>{dailyTimeBands.afternoon}m</strong>
          </div>
          <div className="band-row">
            <span>Evening</span>
            <div className="report-progress-track" aria-hidden="true">
              <span
                className="report-progress-fill"
                style={{
                  width: `${dailyTotalMinutes ? Math.round((dailyTimeBands.evening / dailyTotalMinutes) * 100) : 0}%`,
                }}
              />
            </div>
            <strong>{dailyTimeBands.evening}m</strong>
          </div>

          <div className="report-list" style={{ marginTop: "0.45rem" }}>
            <article className="report-list-row compact">
              <strong>Top Tasks</strong>
              {dailyTopTasks.length ? (
                dailyTopTasks.map((row) => (
                  <span key={`${row.taskId || "none"}-${row.title}`}>
                    {row.title}: {row.minutes} min ({row.sessions} sessions)
                  </span>
                ))
              ) : (
                <span className="muted">No tasks captured in today logs.</span>
              )}
            </article>
          </div>
        </section>

        <section className="report-panel">
          <div className="report-panel-head">
            <h3>Activity Feed</h3>
          </div>
          <div className="report-list activity" style={{ marginTop: "0.3rem" }}>
            {dailyLogsFiltered.length ? (
              dailyLogsFiltered.map((log) => (
                <article key={log.id} className="report-list-row">
                  <strong>{String(log.task?.title || `Task #${log.task_id || "-"}`)}</strong>
                  <span>
                    {Math.round(Number(log.duration_minutes || 0))} min • {formatOptionalDate(log.start_time)}
                  </span>
                  {log.summary ? <span className="muted">{log.summary}</span> : null}
                </article>
              ))
            ) : (
              <p className="report-empty">No logs for today (or no logs match the current filter).</p>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
