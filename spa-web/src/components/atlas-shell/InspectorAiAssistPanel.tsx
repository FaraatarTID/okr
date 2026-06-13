"use client";

type AiSyncReportView = {
  total: number;
  analyzed: number;
  applied: number;
  planned: number;
  missingAiScore: number;
  skippedDeltaCap: number;
  skippedDecrease: number;
  unchanged: number;
  failed: string[];
};

type AiTaskSuggestionView = {
  taskRef: string;
  reason: string;
  confidence: number | null;
} | null;

type InspectorAiAssistPanelProps = {
  aiSyncMaxDelta: number;
  aiSyncPending: boolean;
  aiSuggestPending: boolean;
  hasUser: boolean;
  hasAtlasRuntime: boolean;
  hasAiUndoItems: boolean;
  hasTaskRefs: boolean;
  aiSyncReport: AiSyncReportView | null;
  aiSuggestion: AiTaskSuggestionView;
  aiSyncError: string;
  aiSyncMessage: string;
  onPreviewAiSync: () => void;
  onApplyAiSync: () => void;
  onUndoAiSync: () => void;
  onSuggestNextTask: () => void;
};

export default function InspectorAiAssistPanel({
  aiSyncMaxDelta,
  aiSyncPending,
  aiSuggestPending,
  hasUser,
  hasAtlasRuntime,
  hasAiUndoItems,
  hasTaskRefs,
  aiSyncReport,
  aiSuggestion,
  aiSyncError,
  aiSyncMessage,
  onPreviewAiSync,
  onApplyAiSync,
  onUndoAiSync,
  onSuggestNextTask,
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

      <div className="grid-2" style={{ marginTop: "0.45rem", gap: "0.45rem" }}>
        <button
          className="primary-button"
          type="button"
          onClick={onPreviewAiSync}
          disabled={aiSyncPending || aiSuggestPending || !hasUser || !hasAtlasRuntime}
        >
          {aiSyncPending ? "Working..." : "Preview AI Sync"}
        </button>
        <button
          className="primary-button"
          type="button"
          onClick={onApplyAiSync}
          disabled={aiSyncPending || aiSuggestPending || !hasUser || !hasAtlasRuntime}
        >
          {aiSyncPending ? "Working..." : "Apply AI Sync"}
        </button>
        <button
          className="primary-button"
          type="button"
          onClick={onUndoAiSync}
          disabled={aiSyncPending || aiSuggestPending || !hasAiUndoItems || !hasUser}
        >
          {aiSyncPending ? "Working..." : "Undo Sync"}
        </button>
        <button
          className="primary-button"
          type="button"
          onClick={onSuggestNextTask}
          disabled={aiSyncPending || aiSuggestPending || !hasTaskRefs || !hasUser}
        >
          {aiSuggestPending ? "Working..." : "Suggest Next Task"}
        </button>
      </div>

      {aiSyncReport ? (
        <div style={{ marginTop: "0.34rem", fontSize: "0.8rem", color: "var(--ink-soft)" }}>
          <p style={{ margin: "0 0 0.15rem" }}>
            Analyzed {aiSyncReport.analyzed} of {aiSyncReport.total} KRs.
          </p>
          {aiSyncReport.planned > 0 && (
            <p style={{ margin: "0 0 0.15rem", color: "var(--accent)" }}>
              {aiSyncReport.planned} change{aiSyncReport.planned !== 1 ? "s" : ""} ready to apply.
            </p>
          )}
          {aiSyncReport.applied > 0 && (
            <p style={{ margin: "0 0 0.15rem", color: "var(--accent)" }}>
              {aiSyncReport.applied} update{aiSyncReport.applied !== 1 ? "s" : ""} applied.
            </p>
          )}
          {aiSyncReport.unchanged > 0 && (
            <p style={{ margin: "0 0 0.15rem" }}>
              {aiSyncReport.unchanged} unchanged (AI score matches current).
            </p>
          )}
          {aiSyncReport.missingAiScore > 0 && (
            <p style={{ margin: "0 0 0.15rem" }}>
              {aiSyncReport.missingAiScore} skipped (no AI score available).
            </p>
          )}
          {aiSyncReport.skippedDeltaCap > 0 && (
            <p style={{ margin: "0 0 0.15rem" }}>
              {aiSyncReport.skippedDeltaCap} skipped (change exceeds safety cap).
            </p>
          )}
          {aiSyncReport.skippedDecrease > 0 && (
            <p style={{ margin: "0 0 0.15rem" }}>
              {aiSyncReport.skippedDecrease} skipped (AI suggests lower value; use Preview to review).
            </p>
          )}
        </div>
      ) : null}
      {aiSuggestion ? (
        <p style={{ margin: "0.34rem 0 0", fontSize: "0.8rem", color: "var(--ink-soft)" }}>
          Suggested: {aiSuggestion.taskRef}
          {aiSuggestion.confidence !== null ? ` (${aiSuggestion.confidence}% confidence)` : ""}
          {aiSuggestion.reason ? ` - ${aiSuggestion.reason}` : ""}
        </p>
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
