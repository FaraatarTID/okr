"use client";

type AiSyncReportView = {
  total: number;
  analyzed: number;
  reanalyzed: number;
  unchanged: number;
  failed: string[];
};

type InspectorAiAssistPanelProps = {
  aiSyncPending: boolean;
  hasUser: boolean;
  hasAtlasRuntime: boolean;
  aiSyncReport: AiSyncReportView | null;
  aiSyncError: string;
  aiSyncMessage: string;
  onRunAiSync: () => void;
};

export default function InspectorAiAssistPanel({
  aiSyncPending,
  hasUser,
  hasAtlasRuntime,
  aiSyncReport,
  aiSyncError,
  aiSyncMessage,
  onRunAiSync,
}: InspectorAiAssistPanelProps) {
  return (
    <div
      style={{
        border: "1px solid var(--line)",
        borderRadius: 10,
        background: "var(--surface)",
        padding: "0.55rem 0.6rem",
        marginBottom: "0.72rem",
      }}
    >
      <p className="kicker" style={{ margin: 0 }}>
        AI Assist
      </p>

      <div style={{ marginTop: "0.45rem" }}>
        <button
          className="primary-button"
          type="button"
          onClick={onRunAiSync}
          disabled={aiSyncPending || !hasUser || !hasAtlasRuntime}
          style={{ flex: "1 1 auto", minWidth: "6rem" }}
        >
          {aiSyncPending ? "Analyzing..." : "AI Analysis"}
        </button>
      </div>

      {aiSyncReport ? (
        <div style={{ marginTop: "0.34rem", fontSize: "0.8rem", color: "var(--ink-soft)" }}>
          {aiSyncReport.reanalyzed > 0 && (
            <p style={{ margin: "0 0 0.15rem" }}>
              Analyzed {aiSyncReport.reanalyzed} KR{aiSyncReport.reanalyzed !== 1 ? "s" : ""} ({aiSyncReport.analyzed - aiSyncReport.reanalyzed} cached).
            </p>
          )}
          {aiSyncReport.reanalyzed === 0 && (
            <p style={{ margin: "0 0 0.15rem" }}>
              All {aiSyncReport.analyzed} KRs have fresh analysis.
            </p>
          )}
          {aiSyncReport.unchanged > 0 && aiSyncReport.reanalyzed > 0 && (
            <p style={{ margin: "0 0 0.15rem" }}>
              {aiSyncReport.unchanged} unchanged (analysis already fresh).
            </p>
          )}
        </div>
      ) : null}
      {aiSyncError ? (
        <p style={{ margin: "0.34rem 0 0", color: "var(--error)", fontSize: "0.82rem" }}>{aiSyncError}</p>
      ) : null}
      {aiSyncMessage ? (
        <p style={{ margin: "0.34rem 0 0", color: "var(--accent)", fontSize: "0.82rem" }}>{aiSyncMessage}</p>
      ) : null}
      {aiSyncReport?.failed?.length ? (
        <div className="atlas-node-list" style={{ marginTop: "0.35rem", maxHeight: "16vh" }}>
          {aiSyncReport.failed.map((row) => (
            <p key={row} style={{ margin: "0.2rem 0", fontSize: "0.78rem", color: "var(--warn)" }}>
              {row}
            </p>
          ))}
        </div>
      ) : null}
    </div>
  );
}
