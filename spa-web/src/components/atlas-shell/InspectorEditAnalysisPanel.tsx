"use client";

import { rtlStyle } from "@/lib/rtl";

type InspectorEditDraftView = {
  title: string;
  description: string;
  progress: string;
  deadline: string;
};

type AnalysisSummaryView = {
  efficiencyScore: number | null;
  effectivenessScore: number | null;
  overallScore: number | null;
  summary: string;
  gapAnalysis: string;
  qualityAssessment: string;
  deadlineWarnings: string[];
  proposedTasks: string[];
};

type InspectorEditAnalysisPanelProps = {
  inspectDraft: InspectorEditDraftView;
  onInspectDraftChange: (patch: Partial<InspectorEditDraftView>) => void;
  onInspectorSave: () => void;
  inspectPending: boolean;
  hasUser: boolean;
  onNodeDelete: () => void;
  deletePending: boolean;
  deleteError: string;
  deleteMessage: string;
  selectedTypeLabel: string;
  selectedNodeType: string;
  inspectError: string;
  inspectMessage: string;
  showAiAnalysis: boolean;
  aiAnalysisTargetLabel: "key result" | "objective";
  onRunAnalysis: () => void;
  inspectAnalysisPending: boolean;
  inspectAnalysisError: string;
  inspectAnalysis: AnalysisSummaryView | null;
};

export default function InspectorEditAnalysisPanel({
  inspectDraft,
  onInspectDraftChange,
  onInspectorSave,
  inspectPending,
  hasUser,
  onNodeDelete,
  deletePending,
  deleteError,
  deleteMessage,
  selectedTypeLabel,
  selectedNodeType,
  inspectError,
  inspectMessage,
  showAiAnalysis,
  aiAnalysisTargetLabel,
  onRunAnalysis,
  inspectAnalysisPending,
  inspectAnalysisError,
  inspectAnalysis,
}: InspectorEditAnalysisPanelProps) {
  return (
    <>
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
          Edit Node
        </p>
        <label
          htmlFor="inspect-title"
          style={{ display: "block", marginTop: "0.36rem", fontSize: "0.78rem", color: "var(--ink-soft)" }}
        >
          Title
        </label>
        <input
          id="inspect-title"
          className="input"
          value={inspectDraft.title}
          onChange={(event) => onInspectDraftChange({ title: event.target.value })}
          style={{ marginTop: "0.2rem" }}
        />

        <label
          htmlFor="inspect-description"
          style={{ display: "block", marginTop: "0.36rem", fontSize: "0.78rem", color: "var(--ink-soft)" }}
        >
          Description
        </label>
        <input
          id="inspect-description"
          className="input"
          value={inspectDraft.description}
          onChange={(event) => onInspectDraftChange({ description: event.target.value })}
          style={{ marginTop: "0.2rem" }}
        />

        {selectedNodeType === "KEY_RESULT" ? (
          <>
            <label
              htmlFor="inspect-progress"
              style={{ display: "block", marginTop: "0.36rem", fontSize: "0.78rem", color: "var(--ink-soft)" }}
            >
              Progress (0-100)
            </label>
            <input
              id="inspect-progress"
              className="input"
              value={inspectDraft.progress}
              onChange={(event) => onInspectDraftChange({ progress: event.target.value })}
              style={{ marginTop: "0.2rem" }}
            />
          </>
        ) : null}

        {selectedNodeType === "TASK" ? (
          <>
            <label
              htmlFor="inspect-deadline"
              style={{ display: "block", marginTop: "0.36rem", fontSize: "0.78rem", color: "var(--ink-soft)" }}
            >
              Deadline (optional)
            </label>
            <input
              id="inspect-deadline"
              type="date"
              className="input"
              value={inspectDraft.deadline}
              onChange={(event) => onInspectDraftChange({ deadline: event.target.value })}
              style={{ marginTop: "0.2rem" }}
            />
          </>
        ) : null}

        <div style={{ display: "flex", gap: "0.45rem", marginTop: "0.46rem", flexWrap: "wrap" }}>
          <button
            className="primary-button"
            type="button"
            onClick={onInspectorSave}
            disabled={inspectPending || !hasUser}
          >
            {inspectPending ? "Saving..." : "Edit"}
          </button>
          <button
            className="primary-button"
            type="button"
            onClick={onNodeDelete}
            disabled={deletePending || !hasUser}
          >
            {deletePending ? "Deleting..." : `Delete ${selectedTypeLabel}`}
          </button>
        </div>

        {inspectError ? (
          <p style={{ margin: "0.34rem 0 0", color: "var(--error)", fontSize: "0.82rem" }}>
            {inspectError}
          </p>
        ) : null}
        {inspectMessage ? (
          <p style={{ margin: "0.34rem 0 0", color: "var(--accent)", fontSize: "0.82rem" }}>
            {inspectMessage}
          </p>
        ) : null}
        {deleteError ? (
          <p style={{ margin: "0.34rem 0 0", color: "var(--error)", fontSize: "0.82rem" }}>
            {deleteError}
          </p>
        ) : null}
        {deleteMessage ? (
          <p style={{ margin: "0.34rem 0 0", color: "var(--accent)", fontSize: "0.82rem" }}>
            {deleteMessage}
          </p>
        ) : null}
      </div>

      {showAiAnalysis ? (
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
            AI Analysis
          </p>
          <p style={{ margin: "0.24rem 0 0.34rem", fontSize: "0.82rem", color: "var(--ink-soft)" }}>
            Generate analysis for the selected {aiAnalysisTargetLabel}.
          </p>
          <button
            className="primary-button"
            type="button"
            onClick={onRunAnalysis}
            disabled={inspectAnalysisPending || !hasUser}
          >
            {inspectAnalysisPending ? "Analyzing..." : "Run Analysis"}
          </button>

          {inspectAnalysisError ? (
            <p style={{ margin: "0.34rem 0 0", color: "var(--error)", fontSize: "0.82rem" }}>
              {inspectAnalysisError}
            </p>
          ) : null}
          {inspectAnalysis ? (
            <>
              <div className="atlas-rollup" style={{ marginTop: "0.45rem" }}>
                <span>Efficiency: {inspectAnalysis.efficiencyScore ?? "-"}</span>
                <span>Effectiveness: {inspectAnalysis.effectivenessScore ?? "-"}</span>
                <span>Overall: {inspectAnalysis.overallScore ?? "-"}</span>
              </div>
              {inspectAnalysis.summary ? (
                <p style={{ margin: "0.32rem 0 0", color: "var(--ink-soft)", fontSize: "0.82rem", ...rtlStyle(inspectAnalysis.summary) }}>
                  {inspectAnalysis.summary}
                </p>
              ) : null}
              {inspectAnalysis.gapAnalysis ? (
                <p style={{ margin: "0.32rem 0 0", color: "var(--ink-soft)", fontSize: "0.82rem", ...rtlStyle(inspectAnalysis.gapAnalysis) }}>
                  Gap: {inspectAnalysis.gapAnalysis}
                </p>
              ) : null}
              {inspectAnalysis.qualityAssessment ? (
                <p style={{ margin: "0.32rem 0 0", color: "var(--ink-soft)", fontSize: "0.82rem", ...rtlStyle(inspectAnalysis.qualityAssessment) }}>
                  Quality: {inspectAnalysis.qualityAssessment}
                </p>
              ) : null}
              {inspectAnalysis.deadlineWarnings.length ? (
                <div style={{ marginTop: "0.35rem" }}>
                  {inspectAnalysis.deadlineWarnings.map((item) => (
                    <p key={item} style={{ margin: "0.2rem 0", fontSize: "0.78rem", color: "var(--warn)", ...rtlStyle(item) }}>
                      {item}
                    </p>
                  ))}
                </div>
              ) : null}
              {inspectAnalysis.proposedTasks.length ? (
                <div style={{ marginTop: "0.35rem" }}>
                  {inspectAnalysis.proposedTasks.map((item) => (
                    <p key={item} style={{ margin: "0.2rem 0", fontSize: "0.78rem", color: "var(--ink-soft)", ...rtlStyle(item) }}>
                      {item}
                    </p>
                  ))}
                </div>
              ) : null}
            </>
          ) : null}
        </div>
      ) : null}
    </>
  );
}
