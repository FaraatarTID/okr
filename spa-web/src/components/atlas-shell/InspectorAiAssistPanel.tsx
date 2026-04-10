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
  rolloutAllowed: boolean;
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
  rolloutAllowed,
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
      <p style={{ margin: "0.24rem 0 0.3rem", fontSize: "0.82rem", color: "var(--ink-soft)" }}>
        Sync KR progress from AI scores, rollback, and auto-suggest next focus task.
      </p>

      <p style={{ margin: "0.24rem 0 0", fontSize: "0.8rem", color: "var(--ink-soft)" }}>
        Uses a fixed safety policy: max {aiSyncMaxDelta}-point change per KR per run; decreases are blocked.
      </p>

      <div className="grid-2" style={{ marginTop: "0.45rem", gap: "0.45rem" }}>
        <button
          className="primary-button"
          type="button"
          onClick={onPreviewAiSync}
          disabled={aiSyncPending || aiSuggestPending || !hasUser || !hasAtlasRuntime || !rolloutAllowed}
        >
          {aiSyncPending ? "Working..." : "Preview AI Sync"}
        </button>
        <button
          className="primary-button"
          type="button"
          onClick={onApplyAiSync}
          disabled={aiSyncPending || aiSuggestPending || !hasUser || !hasAtlasRuntime || !rolloutAllowed}
        >
          {aiSyncPending ? "Working..." : "Apply AI Sync"}
        </button>
        <button
          className="primary-button"
          type="button"
          onClick={onUndoAiSync}
          disabled={aiSyncPending || aiSuggestPending || !hasAiUndoItems || !hasUser || !rolloutAllowed}
        >
          {aiSyncPending ? "Working..." : "Undo Sync"}
        </button>
        <button
          className="primary-button"
          type="button"
          onClick={onSuggestNextTask}
          disabled={aiSyncPending || aiSuggestPending || !hasTaskRefs || !hasUser || !rolloutAllowed}
        >
          {aiSuggestPending ? "Working..." : "Suggest Next Task"}
        </button>
      </div>

      {aiSyncReport ? (
        <p style={{ margin: "0.34rem 0 0", fontSize: "0.8rem", color: "var(--ink-soft)" }}>
          KR sync: analyzed {aiSyncReport.analyzed}/{aiSyncReport.total}, planned {aiSyncReport.planned}, applied{" "}
          {aiSyncReport.applied}, unchanged {aiSyncReport.unchanged}, missing AI score {aiSyncReport.missingAiScore},
          skipped by delta {aiSyncReport.skippedDeltaCap}, skipped by decrease policy{" "}
          {aiSyncReport.skippedDecrease}.
        </p>
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
