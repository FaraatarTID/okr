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
  nodeQuery,
  onNodeQueryChange,
  hasSnapshotPayload,
  nodeTagForType,
}: AtlasFocusMapPanelProps) {
  return (
    <div className="atlas-map-pane">
      <p className="kicker">Focus Map</p>
      <h2 style={{ margin: "0.1rem 0 0.4rem", fontSize: "1.05rem" }}>
        Focus Map Nodes ({filteredRefs.length})
      </h2>
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
                  style={{ paddingLeft: `${treeIndentRem}rem` }}
                >
                  <span className="atlas-node-tag">{nodeTagForType(meta.type)}</span>
                  <span className="atlas-node-title">{meta.title}</span>
                  <span className="atlas-node-progress">{meta.progress}%</span>
                </button>
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
