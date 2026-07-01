"use client";

type FocusMapNodeView = {
  type: string;
  depth: number;
  title: string;
  progress: number;
};

type AtlasFocusMapPanelProps = {
  filteredRefs: string[];
  atlasIndex: Record<string, FocusMapNodeView> | null;
  selectedRef: string;
  onSelectRef: (ref: string) => void;
  onAddChild: (parentRef: string) => void;
  nodeQuery: string;
  onNodeQueryChange: (value: string) => void;
  hasSnapshotPayload: boolean;
  nodeTagForType: (type: string) => string;
};

export default function AtlasFocusMapPanel({
  filteredRefs,
  atlasIndex,
  selectedRef,
  onSelectRef,
  onAddChild,
  nodeQuery,
  onNodeQueryChange,
  hasSnapshotPayload,
  nodeTagForType,
}: AtlasFocusMapPanelProps) {
  return (
    <div className="atlas-map-pane">
      <p className="kicker">Focus Map</p>
      <input
        className="input"
        value={nodeQuery}
        onChange={(event) => onNodeQueryChange(event.target.value)}
        placeholder="Search title, description, owner, or ref"
        style={{ marginBottom: "0.65rem" }}
      />

      <div className="atlas-node-list">
        {filteredRefs.length > 0 && atlasIndex ? (
          filteredRefs.map((ref) => {
            const meta = atlasIndex[ref];
            if (!meta) {
              return null;
            }
            const treeIndentRem = 0.7 + meta.depth * 0.95;
            const treeDepthClass = `depth-${Math.min(meta.depth, 8)}`;
            return (
              <div
                key={ref}
                className={`atlas-tree-row ${treeDepthClass}`}
                data-depth={meta.depth > 0 ? "1" : "0"}
              >
                <button
                  type="button"
                  className={`atlas-node-item atlas-node-item-tree${selectedRef === ref ? " is-active" : ""}`}
                  onClick={() => onSelectRef(ref)}
                  style={{ paddingLeft: `${treeIndentRem}rem`, flex: "1 1 0", minWidth: 0 }}
                >
                  <span className="atlas-node-tag">{nodeTagForType(meta.type)}</span>
                  <span className="atlas-node-title">{meta.title}</span>
                  {(meta.type === "KEY_RESULT" || meta.type === "TASK") && (
                    <span className="atlas-node-progress">{meta.progress}%</span>
                  )}
                </button>
                {meta.type !== "TASK" && (
                  <button
                    type="button"
                    className="atlas-node-add"
                    onClick={() => onAddChild(ref)}
                    title={`Add child to ${meta.title}`}
                    style={{
                      marginLeft: "0.2rem",
                      padding: "0.1rem 0.4rem",
                      fontSize: "0.75rem",
                      lineHeight: 1.4,
                      border: "1px solid var(--line)",
                      borderRadius: 4,
                      background: "var(--surface)",
                      color: "var(--ink-soft)",
                      cursor: "pointer",
                      flexShrink: 0,
                    }}
                  >
                    +
                  </button>
                )}
              </div>
            );
          })
        ) : (
          <p style={{ margin: 0, color: "var(--ink-soft)" }}>
            {hasSnapshotPayload ? "No matching nodes for current filter." : "No snapshot payload yet."}
          </p>
        )}
      </div>
    </div>
  );
}
