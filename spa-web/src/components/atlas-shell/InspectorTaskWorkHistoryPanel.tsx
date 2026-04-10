"use client";

type WorkLogHistoryRowView = {
  id: number;
  duration_minutes?: number | null;
  end_time?: string | null;
  summary?: string | null;
};

type InspectorTaskWorkHistoryPanelProps = {
  inspectTaskWorkLogsPending: boolean;
  inspectTaskWorkLogsError: string;
  inspectTaskWorkLogsActionError: string;
  inspectTaskWorkLogsActionMessage: string;
  inspectTaskWorkHistoryRows: WorkLogHistoryRowView[];
  inspectTaskWorkLogPendingId: number | null;
  hasUser: boolean;
  rolloutAllowed: boolean;
  formatOptionalDate: (value?: string | null) => string;
  onDeleteWorkLog: (workLogId: number) => void;
};

export default function InspectorTaskWorkHistoryPanel({
  inspectTaskWorkLogsPending,
  inspectTaskWorkLogsError,
  inspectTaskWorkLogsActionError,
  inspectTaskWorkLogsActionMessage,
  inspectTaskWorkHistoryRows,
  inspectTaskWorkLogPendingId,
  hasUser,
  rolloutAllowed,
  formatOptionalDate,
  onDeleteWorkLog,
}: InspectorTaskWorkHistoryPanelProps) {
  return (
    <div
      style={{
        marginTop: "0.72rem",
        border: "1px solid var(--line)",
        borderRadius: 10,
        background: "var(--surface)",
        padding: "0.55rem 0.6rem",
      }}
    >
      <p className="kicker" style={{ margin: 0 }}>
        Work History
      </p>
      <p style={{ margin: "0.24rem 0 0", fontSize: "0.8rem", color: "var(--ink-soft)" }}>
        ended_at | duration | summary
      </p>
      {inspectTaskWorkLogsPending ? (
        <p style={{ margin: "0.36rem 0 0", color: "var(--ink-soft)", fontSize: "0.82rem" }}>
          Loading work history...
        </p>
      ) : null}
      {inspectTaskWorkLogsError ? (
        <p style={{ margin: "0.36rem 0 0", color: "var(--error)", fontSize: "0.82rem" }}>
          {inspectTaskWorkLogsError}
        </p>
      ) : null}
      {inspectTaskWorkLogsActionError ? (
        <p style={{ margin: "0.36rem 0 0", color: "var(--error)", fontSize: "0.82rem" }}>
          {inspectTaskWorkLogsActionError}
        </p>
      ) : null}
      {inspectTaskWorkLogsActionMessage ? (
        <p style={{ margin: "0.36rem 0 0", color: "var(--accent)", fontSize: "0.82rem" }}>
          {inspectTaskWorkLogsActionMessage}
        </p>
      ) : null}
      {!inspectTaskWorkLogsPending && !inspectTaskWorkLogsError && !inspectTaskWorkHistoryRows.length ? (
        <p style={{ margin: "0.36rem 0 0", color: "var(--ink-soft)", fontSize: "0.82rem" }}>
          No work logs found for this task.
        </p>
      ) : null}
      {inspectTaskWorkHistoryRows.length ? (
        <div className="atlas-node-list" style={{ marginTop: "0.4rem", maxHeight: "24vh" }}>
          {inspectTaskWorkHistoryRows.map((log) => {
            const endedAt = log.end_time ? formatOptionalDate(log.end_time) : "Running";
            const duration = Math.round(Number(log.duration_minutes || 0) * 10) / 10;
            const summaryFull = String(log.summary || "").trim() || "-";
            const summaryPreview =
              summaryFull.length > 120 ? `${summaryFull.slice(0, 117).trimEnd()}...` : summaryFull;
            return (
              <div
                key={log.id}
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr auto",
                  gap: "0.45rem",
                  alignItems: "start",
                  padding: "0.3rem 0",
                  borderBottom: "1px solid var(--line)",
                }}
              >
                <details>
                  <summary style={{ cursor: "pointer", fontSize: "0.82rem", color: "var(--ink)" }}>
                    <strong>{endedAt}</strong> | {duration}m | {summaryPreview}
                  </summary>
                  <p
                    style={{
                      margin: "0.34rem 0 0",
                      fontSize: "0.82rem",
                      color: "var(--ink-soft)",
                      whiteSpace: "pre-wrap",
                    }}
                  >
                    {summaryFull}
                  </p>
                </details>
                <button
                  className="primary-button"
                  type="button"
                  onClick={() => onDeleteWorkLog(log.id)}
                  disabled={inspectTaskWorkLogPendingId === log.id || !hasUser || !rolloutAllowed}
                  style={{ minWidth: 84 }}
                >
                  {inspectTaskWorkLogPendingId === log.id ? "Deleting..." : "Delete"}
                </button>
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
