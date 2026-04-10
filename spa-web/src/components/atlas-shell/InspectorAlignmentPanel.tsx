"use client";

type AlignmentObjectiveView = {
  id: number;
  title?: string;
};

type AlignmentEdgeView = {
  id: number;
  parent_id: number;
  child_id: number;
  alignment_type?: string;
};

type AlignmentContextView = {
  parents?: AlignmentObjectiveView[];
  children?: AlignmentObjectiveView[];
  all_objectives?: AlignmentObjectiveView[];
  edges?: AlignmentEdgeView[];
} | null;

type InspectorAlignmentPanelProps = {
  alignmentPending: boolean;
  alignmentError: string;
  alignmentContext: AlignmentContextView;
  alignmentDirection: "parent" | "child";
  alignmentTargetObjectiveId: string;
  onAlignmentDirectionChange: (value: "parent" | "child") => void;
  onAlignmentTargetObjectiveIdChange: (value: string) => void;
  onAlignmentCreate: () => void;
  onAlignmentDelete: (edgeId: number) => void;
};

export default function InspectorAlignmentPanel({
  alignmentPending,
  alignmentError,
  alignmentContext,
  alignmentDirection,
  alignmentTargetObjectiveId,
  onAlignmentDirectionChange,
  onAlignmentTargetObjectiveIdChange,
  onAlignmentCreate,
  onAlignmentDelete,
}: InspectorAlignmentPanelProps) {
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
        Alignment
      </p>
      {alignmentPending ? (
        <p style={{ margin: "0.3rem 0 0", color: "var(--ink-soft)", fontSize: "0.82rem" }}>
          Loading alignment...
        </p>
      ) : null}
      {alignmentError ? (
        <p style={{ margin: "0.3rem 0 0", color: "var(--error)", fontSize: "0.82rem" }}>{alignmentError}</p>
      ) : null}
      <p style={{ margin: "0.3rem 0 0", fontSize: "0.82rem", color: "var(--ink-soft)" }}>
        Parents: {(alignmentContext?.parents || []).length} | Children: {(alignmentContext?.children || []).length}
      </p>
      <div style={{ display: "flex", gap: "0.4rem", marginTop: "0.4rem", flexWrap: "wrap" }}>
        <select
          className="input"
          value={alignmentDirection}
          onChange={(event) => onAlignmentDirectionChange(event.target.value as "parent" | "child")}
          style={{ maxWidth: 180 }}
        >
          <option value="parent">Add parent link</option>
          <option value="child">Add child link</option>
        </select>
        <select
          className="input"
          value={alignmentTargetObjectiveId}
          onChange={(event) => onAlignmentTargetObjectiveIdChange(event.target.value)}
          style={{ minWidth: 260 }}
        >
          <option value="">Choose objective...</option>
          {(alignmentContext?.all_objectives || []).map((item) => (
            <option key={item.id} value={item.id}>
              {item.title || `Objective #${item.id}`}
            </option>
          ))}
        </select>
        <button className="primary-button" type="button" onClick={onAlignmentCreate}>
          Add link
        </button>
      </div>
      {(alignmentContext?.edges || []).length ? (
        <div className="atlas-node-list" style={{ marginTop: "0.45rem", maxHeight: "28vh" }}>
          {(alignmentContext?.edges || []).map((edge) => (
            <div key={edge.id} style={{ padding: "0.35rem 0", borderBottom: "1px solid var(--line)" }}>
              <span style={{ fontSize: "0.8rem", color: "var(--ink-soft)" }}>
                {edge.parent_id} {" -> "} {edge.child_id} ({edge.alignment_type || "SUPPORTS"})
              </span>
              <button
                className="primary-button"
                type="button"
                style={{ marginLeft: "0.4rem" }}
                onClick={() => onAlignmentDelete(edge.id)}
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
