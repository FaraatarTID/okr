"use client";

type TimelineStatusFilter = "all" | "todo" | "in_progress" | "done" | "blocked" | "overdue";

type TimelineRowView = {
  id: number;
  title: string;
  status: string;
  progress: number;
  assigneeName: string;
  keyResultTitle: string;
  objectiveTitle: string;
  goalTitle: string;
  startAt: Date;
  endAt: Date;
  isProjectedEnd: boolean;
  isOverdue: boolean;
};

type TimelineStatusCountsView = {
  todo: number;
  inProgress: number;
  done: number;
  blocked: number;
  overdue: number;
};

type TimelineWindowView = {
  start: Date;
  end: Date;
  spanMs: number;
  todayLeftPct: number;
};

type TimelineLogView = {
  id: number;
  task_id?: number | null;
  duration_minutes?: number | null;
  start_time?: string | null;
  task?: { title?: string | null } | null;
};

type TimelineModePanelProps = {
  timelineRows: TimelineRowView[];
  timelineRowsFiltered: TimelineRowView[];
  timelineStatusCounts: TimelineStatusCountsView;
  timelineQuery: string;
  onTimelineQueryChange: (value: string) => void;
  timelineStatusFilter: TimelineStatusFilter;
  onTimelineStatusFilterChange: (value: TimelineStatusFilter) => void;
  timelineWindow: TimelineWindowView | null;
  timelineLogs: TimelineLogView[];
  timelineStatusLabel: (value: string) => string;
  toDateShortLabel: (value: Date) => string;
  formatOptionalDate: (value: unknown) => string;
  onOpenTaskInAtlas: (taskId: number) => void;
};

export default function TimelineModePanel({
  timelineRows,
  timelineRowsFiltered,
  timelineStatusCounts,
  timelineQuery,
  onTimelineQueryChange,
  timelineStatusFilter,
  onTimelineStatusFilterChange,
  timelineWindow,
  timelineLogs,
  timelineStatusLabel,
  toDateShortLabel,
  formatOptionalDate,
  onOpenTaskInAtlas,
}: TimelineModePanelProps) {
  return (
    <div className="timeline-workspace">
      <div className="timeline-summary" aria-label="Timeline summary">
        <span>Tasks in cycle: {timelineRows.length}</span>
        <span>Visible: {timelineRowsFiltered.length}</span>
        <span>Done: {timelineStatusCounts.done}</span>
        <span>In progress: {timelineStatusCounts.inProgress}</span>
        <span>Blocked/Overdue: {timelineStatusCounts.blocked + timelineStatusCounts.overdue}</span>
      </div>
      <div className="timeline-controls" style={{ marginTop: "0.45rem" }}>
        <input
          className="input"
          value={timelineQuery}
          onChange={(event) => onTimelineQueryChange(event.target.value)}
          placeholder="Filter timeline by task, owner, objective, goal, or status"
        />
        <select
          className="input"
          value={timelineStatusFilter}
          onChange={(event) =>
            onTimelineStatusFilterChange(
              event.target.value as "all" | "todo" | "in_progress" | "done" | "blocked" | "overdue",
            )
          }
        >
          <option value="all">All statuses</option>
          <option value="todo">Todo</option>
          <option value="in_progress">In Progress</option>
          <option value="done">Done</option>
          <option value="blocked">Blocked</option>
          <option value="overdue">Overdue</option>
        </select>
      </div>
      {timelineWindow ? (
        <div className="timeline-board" style={{ marginTop: "0.45rem" }}>
          <div className="timeline-board-header">
            <div>
              <p className="kicker">Schedule</p>
              <strong>Project Gantt</strong>
            </div>
            <div className="timeline-board-range">
              <span>{toDateShortLabel(timelineWindow.start)} to {toDateShortLabel(timelineWindow.end)}</span>
              <span className="timeline-today-key"><i aria-hidden="true" /> Today</span>
            </div>
          </div>
          <div className="timeline-rows">
            {timelineRowsFiltered.map((row) => {
              const startPct =
                ((row.startAt.getTime() - timelineWindow.start.getTime()) / timelineWindow.spanMs) * 100;
              const endPct =
                ((row.endAt.getTime() - timelineWindow.start.getTime()) / timelineWindow.spanMs) * 100;
              const leftPct = Math.max(0, Math.min(100, startPct));
              const widthPct = Math.max(1.2, Math.min(100 - leftPct, endPct - leftPct));
              const statusClass = row.status.toLowerCase().replace("_", "-");
              return (
                <div key={row.id} className="timeline-row">
                  <div className="timeline-meta">
                    <strong>{row.title}</strong>
                    <div style={{ fontSize: "0.78rem", color: "var(--ink-soft)" }}>
                      {timelineStatusLabel(row.status)} • {row.assigneeName}
                    </div>
                    <div style={{ fontSize: "0.75rem", color: "var(--ink-soft)" }}>
                      {row.objectiveTitle || row.keyResultTitle || row.goalTitle || "No lineage"}
                    </div>
                    <button
                      className="primary-button"
                      type="button"
                      style={{ marginTop: "0.3rem", padding: "0.32rem 0.48rem", fontSize: "0.72rem" }}
                      onClick={() => onOpenTaskInAtlas(row.id)}
                    >
                      Open in Atlas
                    </button>
                  </div>
                  <div className="timeline-lane">
                    <div className="timeline-today-line" style={{ left: `${timelineWindow.todayLeftPct}%` }} />
                    <div
                      className={`timeline-bar timeline-status-${statusClass}${row.isProjectedEnd ? " is-projected" : ""}${row.isOverdue ? " is-overdue" : ""}`}
                      style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
                      title={`${row.title}: ${toDateShortLabel(row.startAt)} -> ${toDateShortLabel(row.endAt)}`}
                    >
                      <span className="timeline-bar-label">{Math.round(row.progress)}%</span>
                    </div>
                  </div>
                </div>
              );
            })}
            {!timelineRowsFiltered.length ? (
              <p style={{ margin: "0.3rem 0 0", color: "var(--ink-soft)" }}>
                No tasks match current timeline filters.
              </p>
            ) : null}
          </div>
        </div>
      ) : (
        <p style={{ margin: "0.45rem 0 0", color: "var(--ink-soft)" }}>
          {timelineQuery || timelineStatusFilter !== "all"
            ? "No tasks match current timeline filters."
            : "No tasks found for the current cycle."}
        </p>
      )}

      <section className="timeline-worklog-section" aria-labelledby="timeline-worklog-title">
        <div className="timeline-section-heading">
          <div>
            <p className="kicker">Evidence</p>
            <h3 id="timeline-worklog-title">Recent work logs</h3>
          </div>
          <span>{timelineLogs.length} entries</span>
        </div>
        <div className="timeline-worklog-list">
        {timelineLogs.length ? (
          timelineLogs.slice(0, 40).map((log) => (
            <div key={log.id} className="timeline-worklog-row">
              <strong>{String(log.task?.title || `Task #${log.task_id || "-"}`)}</strong>
              <div style={{ fontSize: "0.78rem", color: "var(--ink-soft)" }}>
                {formatOptionalDate(log.start_time)} • {Math.round(Number(log.duration_minutes || 0))} min
              </div>
            </div>
          ))
        ) : (
          <p style={{ margin: 0, color: "var(--ink-soft)" }}>No recent work logs for current actor.</p>
        )}
        </div>
      </section>
    </div>
  );
}
