"use client";

type AlignmentEntityView = {
  id: number;
  title?: string;
};

type AlignmentEdgeView = {
  id: number;
  parent_id: number;
  child_id: number;
  alignment_type?: string;
};

type ObjectiveAlignmentLinkView = {
  id: number;
  objective_id: number;
  linked_entity_type: string;
  linked_entity_id: number;
  direction: string;
  created_at?: string;
  created_by?: string;
};

type AlignmentContextView = {
  parents?: AlignmentEntityView[];
  children?: AlignmentEntityView[];
  all_objectives?: AlignmentEntityView[];
  edges?: AlignmentEdgeView[];
  available_goals?: AlignmentEntityView[];
  available_key_results?: AlignmentEntityView[];
  objective_links?: ObjectiveAlignmentLinkView[];
} | null;

type InspectorAlignmentPanelProps = {
  alignmentPending: boolean;
  alignmentError: string;
  alignmentContext: AlignmentContextView;
  alignmentDirection: "parent" | "child";
  alignmentTargetObjectiveId: string;
  alignmentType: string;
  onAlignmentDirectionChange: (value: "parent" | "child") => void;
  onAlignmentTargetObjectiveIdChange: (value: string) => void;
  onAlignmentTypeChange: (value: string) => void;
  onAlignmentCreate: () => void;
  onAlignmentDelete: (edgeId: number) => void;
  objLinkDirection: "parent" | "child";
  objLinkTargetId: string;
  objLinkPending: boolean;
  objLinkError: string;
  onObjLinkDirectionChange: (value: "parent" | "child") => void;
  onObjLinkTargetIdChange: (value: string) => void;
  onObjLinkCreate: () => void;
  onObjLinkDelete: (linkId: number) => void;
};

export default function InspectorAlignmentPanel({
  alignmentPending,
  alignmentError,
  alignmentContext,
  alignmentDirection,
  alignmentTargetObjectiveId,
  alignmentType,
  onAlignmentDirectionChange,
  onAlignmentTargetObjectiveIdChange,
  onAlignmentTypeChange,
  onAlignmentCreate,
  onAlignmentDelete,
  objLinkDirection,
  objLinkTargetId,
  objLinkPending,
  objLinkError,
  onObjLinkDirectionChange,
  onObjLinkTargetIdChange,
  onObjLinkCreate,
  onObjLinkDelete,
}: InspectorAlignmentPanelProps) {
  const parentGoals = alignmentContext?.available_goals || [];
  const childKeyResults = alignmentContext?.available_key_results || [];
  const objLinks = alignmentContext?.objective_links || [];

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

      {/* Cross-hierarchy links: Goal ↔ Objective ↔ KR */}
      <div style={{ marginTop: "0.5rem", borderTop: "1px solid var(--line)", paddingTop: "0.4rem" }}>
        <p style={{ margin: "0 0 0.3rem", fontSize: "0.78rem", fontWeight: 600, color: "var(--ink-soft)" }}>
          Cross-Hierarchy Links
        </p>
        {objLinkError ? (
          <p style={{ margin: "0.2rem 0", color: "var(--error)", fontSize: "0.82rem" }}>{objLinkError}</p>
        ) : null}
        <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
          <select
            className="input"
            value={objLinkDirection}
            onChange={(event) => onObjLinkDirectionChange(event.target.value as "parent" | "child")}
            style={{ maxWidth: 180 }}
          >
            <option value="parent">Add parent link</option>
            <option value="child">Add child link</option>
          </select>
          <select
            className="input"
            value={objLinkTargetId}
            onChange={(event) => onObjLinkTargetIdChange(event.target.value)}
            style={{ minWidth: 260 }}
          >
            <option value="">
              {objLinkDirection === "parent" ? "Choose Goal..." : "Choose Key Result..."}
            </option>
            {(objLinkDirection === "parent" ? parentGoals : childKeyResults).map((item) => (
              <option key={item.id} value={item.id}>
                {item.title || `${objLinkDirection === "parent" ? "Goal" : "Key Result"} #${item.id}`}
              </option>
            ))}
          </select>
          <button
            className="primary-button"
            type="button"
            onClick={onObjLinkCreate}
            disabled={objLinkPending}
          >
            {objLinkPending ? "Adding..." : "Add link"}
          </button>
        </div>
        {objLinks.length > 0 ? (
          <div className="atlas-node-list" style={{ marginTop: "0.45rem", maxHeight: "28vh" }}>
            {objLinks.map((link) => (
              <div key={link.id} style={{ padding: "0.35rem 0", borderBottom: "1px solid var(--line)" }}>
                <span style={{ fontSize: "0.8rem", color: "var(--ink-soft)" }}>
                  {link.direction === "parent" ? "Parent" : "Child"}: {link.linked_entity_type} #{link.linked_entity_id}
                </span>
                <button
                  className="primary-button"
                  type="button"
                  style={{ marginLeft: "0.4rem" }}
                  onClick={() => onObjLinkDelete(link.id)}
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        ) : null}
      </div>

      {/* Objective-to-objective edges */}
      <div style={{ marginTop: "0.5rem", borderTop: "1px solid var(--line)", paddingTop: "0.4rem" }}>
        <p style={{ margin: "0 0 0.3rem", fontSize: "0.78rem", fontWeight: 600, color: "var(--ink-soft)" }}>
          Objective-to-Objective Links
        </p>
        <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
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
          <select
            className="input"
            value={alignmentType}
            onChange={(event) => onAlignmentTypeChange(event.target.value)}
            style={{ maxWidth: 160 }}
          >
            <option value="SUPPORTS">Supports</option>
            <option value="CONTRIBUTES">Contributes</option>
          </select>
          <button className="primary-button" type="button" onClick={onAlignmentCreate}>
            Add link
          </button>
        </div>
        {(alignmentContext?.edges || []).length > 0 ? (
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
    </div>
  );
}
