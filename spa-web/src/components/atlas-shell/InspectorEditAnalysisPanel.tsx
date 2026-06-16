"use client";

import { rtlStyle } from "@/lib/rtl";

type InspectorEditDraftView = {
  title: string;
  description: string;
  progress: string;
  startValue: string;
  targetValue: string;
  deadline: string;
  estimatedMinutes: string;
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
  inspectAnalysis: AnalysisSummaryView | null;
  onRunAnalysis?: () => void;
  inspectAnalysisPending?: boolean;
  inspectAnalysisError?: string;
};

function AnalysisDetailView({ analysis }: { analysis: AnalysisSummaryView }) {
  return (
    <>
      <div className="atlas-rollup" style={{ marginTop: "0.45rem" }}>
        <span>Efficiency: {analysis.efficiencyScore ?? "-"}</span>
        <span>Effectiveness: {analysis.effectivenessScore ?? "-"}</span>
        <span>Overall: {analysis.overallScore ?? "-"}</span>
      </div>
      {analysis.summary ? (
        <p style={{ margin: "0.32rem 0 0", color: "var(--ink-soft)", fontSize: "0.82rem", ...rtlStyle(analysis.summary) }}>
          {analysis.summary}
        </p>
      ) : null}
      {analysis.gapAnalysis ? (
        <p style={{ margin: "0.32rem 0 0", color: "var(--ink-soft)", fontSize: "0.82rem", ...rtlStyle(analysis.gapAnalysis) }}>
          Gap: {analysis.gapAnalysis}
        </p>
      ) : null}
      {analysis.qualityAssessment ? (
        <p style={{ margin: "0.32rem 0 0", color: "var(--ink-soft)", fontSize: "0.82rem", ...rtlStyle(analysis.qualityAssessment) }}>
          Quality: {analysis.qualityAssessment}
        </p>
      ) : null}
      {analysis.deadlineWarnings.length ? (
        <div style={{ marginTop: "0.35rem" }}>
          {analysis.deadlineWarnings.map((item) => (
            <p key={item} style={{ margin: "0.2rem 0", fontSize: "0.78rem", color: "var(--warn)", ...rtlStyle(item) }}>
              {item}
            </p>
          ))}
        </div>
      ) : null}
      {analysis.proposedTasks.length ? (
        <div style={{ marginTop: "0.35rem" }}>
          {analysis.proposedTasks.map((item) => (
            <p key={item} style={{ margin: "0.2rem 0", fontSize: "0.78rem", color: "var(--ink-soft)", ...rtlStyle(item) }}>
              {item}
            </p>
          ))}
        </div>
      ) : null}
    </>
  );
}

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
  inspectAnalysis,
  onRunAnalysis,
  inspectAnalysisPending = false,
  inspectAnalysisError = "",
}: InspectorEditAnalysisPanelProps) {
  const isKr = selectedNodeType === "KEY_RESULT";
  const showRunAnalysis = isKr && onRunAnalysis;

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

        {isKr ? (
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
            <label
              htmlFor="inspect-start-value"
              style={{ display: "block", marginTop: "0.36rem", fontSize: "0.78rem", color: "var(--ink-soft)" }}
            >
              Start Value
            </label>
            <input
              id="inspect-start-value"
              type="number"
              className="input"
              value={inspectDraft.startValue}
              onChange={(event) => onInspectDraftChange({ startValue: event.target.value })}
              style={{ marginTop: "0.2rem" }}
              placeholder="Starting point"
            />
            <label
              htmlFor="inspect-target-value"
              style={{ display: "block", marginTop: "0.36rem", fontSize: "0.78rem", color: "var(--ink-soft)" }}
            >
              Target Value
            </label>
            <input
              id="inspect-target-value"
              type="number"
              className="input"
              value={inspectDraft.targetValue}
              onChange={(event) => onInspectDraftChange({ targetValue: event.target.value })}
              style={{ marginTop: "0.2rem" }}
              placeholder="Goal to reach"
            />
            {inspectDraft.startValue !== "" && inspectDraft.targetValue !== "" && Number(inspectDraft.targetValue) !== Number(inspectDraft.startValue) && (
              <p style={{ margin: "0.25rem 0 0", fontSize: "0.75rem", color: Number(inspectDraft.targetValue) > Number(inspectDraft.startValue) ? "var(--accent)" : "var(--error)" }}>
                {Number(inspectDraft.targetValue) > Number(inspectDraft.startValue)
                  ? "Higher is better"
                  : "Lower is better"}
              </p>
            )}
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
            <label
              htmlFor="inspect-estimated-minutes"
              style={{ display: "block", marginTop: "0.36rem", fontSize: "0.78rem", color: "var(--ink-soft)" }}
            >
              Estimated Minutes
            </label>
            <input
              id="inspect-estimated-minutes"
              type="number"
              className="input"
              value={inspectDraft.estimatedMinutes}
              onChange={(event) => onInspectDraftChange({ estimatedMinutes: event.target.value })}
              style={{ marginTop: "0.2rem" }}
              min={0}
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

      {isKr && (
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

          {inspectAnalysis ? (
            <AnalysisDetailView analysis={inspectAnalysis} />
          ) : showRunAnalysis ? (
            <>
              <p style={{ margin: "0.24rem 0 0.34rem", fontSize: "0.82rem", color: "var(--ink-soft)" }}>
                No analysis yet for this Key Result.
              </p>
              <button
                className="primary-button"
                type="button"
                onClick={onRunAnalysis}
                disabled={inspectAnalysisPending || !hasUser}
              >
                {inspectAnalysisPending ? "Analyzing..." : "Run Analysis"}
              </button>
            </>
          ) : (
            <p style={{ margin: "0.24rem 0 0", fontSize: "0.82rem", color: "var(--ink-soft)" }}>
              No analysis yet.
            </p>
          )}

          {inspectAnalysisError ? (
            <p style={{ margin: "0.34rem 0 0", color: "var(--error)", fontSize: "0.82rem" }}>
              {inspectAnalysisError}
            </p>
          ) : null}
        </div>
      )}
    </>
  );
}
