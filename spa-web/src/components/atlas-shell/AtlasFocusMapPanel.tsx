"use client";

import { useMemo, useState } from "react";

type FocusMapNodeView = {
  type: string;
  depth: number;
  title: string;
  progress: number;
  parent?: string | null;
  children?: string[];
  ownerName?: string;
};

type OrbitNode = {
  ref: string;
  type: string;
  title: string;
  progress: number;
  ownerName: string;
  depth: number;
  parent: string | null;
  children: string[];
};

type Point = { x: number; y: number };
type PositionedNode = OrbitNode & { x: number; y: number; radius: number };
type OrbitLink = { key: string; from: Point; to: Point; type: string };
type OrbitLayout = { nodes: PositionedNode[]; links: OrbitLink[]; width: number; height: number };

type AtlasFocusMapPanelProps = {
  filteredRefs: string[];
  atlasIndex: Record<string, FocusMapNodeView> | null;
  atlasRoots?: string[];
  selectedRef: string;
  onSelectRef: (ref: string) => void;
  onAddChild: (parentRef: string) => void;
  onCreateGoal: () => void;
  nodeQuery: string;
  onNodeQueryChange: (value: string) => void;
  hasSnapshotPayload: boolean;
  nodeTagForType: (type: string) => string;
};

const VIEW_WIDTH = 1040;
const LAYER_STEP = 205;
const ROW_STEP = 122;
const MAP_MARGIN_X = 132;
const MAP_MARGIN_Y = 112;
const TYPE_LABEL: Record<string, string> = {
  GOAL: "Goal",
  OBJECTIVE: "Objective",
  KEY_RESULT: "Key result",
  TASK: "Task",
};

function buildVisibleTree(
  refs: string[],
  index: Record<string, FocusMapNodeView>,
  roots?: string[],
): OrbitNode[] {
  const allowed = new Set(refs.filter((ref) => Boolean(index[ref])));
  const discovered = new Set<string>();
  const nodes: OrbitNode[] = [];
  const startRefs = roots?.filter((ref) => allowed.has(ref)) ?? [];
  const fallbackRefs = refs.filter((ref) => index[ref]?.depth === 0);
  const stack = [...(startRefs.length ? startRefs : fallbackRefs)].reverse();

  while (stack.length && nodes.length < 600) {
    const ref = stack.pop();
    if (!ref || discovered.has(ref) || !allowed.has(ref)) continue;
    const meta = index[ref];
    if (!meta) continue;
    discovered.add(ref);
    const children = (meta.children || []).filter((child) => allowed.has(child));
    nodes.push({
      ref,
      type: meta.type,
      title: meta.title || "Untitled",
      progress: Math.max(0, Math.min(100, Number(meta.progress) || 0)),
      ownerName: meta.ownerName || "",
      depth: Math.max(0, meta.depth),
      parent: meta.parent || null,
      children,
    });
    for (let i = children.length - 1; i >= 0; i -= 1) stack.push(children[i]);
  }

  // A text search may leave a matching descendant without its ancestors. Keep
  // those results reachable in the Outline rather than silently dropping them.
  for (const ref of refs) {
    if (nodes.length >= 600 || discovered.has(ref) || !index[ref]) continue;
    const meta = index[ref];
    discovered.add(ref);
    nodes.push({
      ref,
      type: meta.type,
      title: meta.title || "Untitled",
      progress: Math.max(0, Math.min(100, Number(meta.progress) || 0)),
      ownerName: meta.ownerName || "",
      depth: Math.max(0, meta.depth),
      parent: meta.parent || null,
      children: [],
    });
  }
  return nodes;
}

function makeOrbitLayout(nodes: OrbitNode[], roots: string[], index: Record<string, FocusMapNodeView>): OrbitLayout {
  if (!nodes.length) return { nodes: [], links: [], width: VIEW_WIDTH, height: 420 };
  const byRef = new Map(nodes.map((node) => [node.ref, node]));
  const rootRefs = roots.filter((ref) => byRef.has(ref));
  const actualRoots = rootRefs.length ? rootRefs : nodes.filter((node) => node.depth === 0).map((node) => node.ref);
  const ordered: OrbitNode[] = [];
  const seen = new Set<string>();
  const queue = [...actualRoots];
  while (queue.length && ordered.length < 600) {
    const ref = queue.shift();
    if (!ref || seen.has(ref)) continue;
    const node = byRef.get(ref);
    if (!node) continue;
    seen.add(ref);
    ordered.push(node);
    queue.push(...node.children);
  }
  for (const node of nodes) if (!seen.has(node.ref)) ordered.push(node);

  const ancestors = (ref: string): number => {
    let depth = 0;
    let current = byRef.get(ref)?.parent || null;
    const visited = new Set<string>();
    while (current && !visited.has(current)) {
      visited.add(current);
      depth += 1;
      current = byRef.get(current)?.parent || index[current]?.parent || null;
    }
    return depth;
  };
  const groups = new Map<number, OrbitNode[]>();
  for (const node of ordered) {
    const depth = Math.min(3, Math.max(0, node.parent && !byRef.has(node.parent) ? ancestors(node.ref) : node.depth));
    groups.set(depth, [...(groups.get(depth) || []), node]);
  }
  const maxRows = Math.max(...Array.from(groups.values(), (group) => group.length), 1);
  const height = Math.max(420, 2 * MAP_MARGIN_Y + (maxRows - 1) * ROW_STEP);
  const positioned: PositionedNode[] = [];
  const positionByRef = new Map<string, PositionedNode>();
  for (const [depth, group] of groups) {
    group.forEach((node, row) => {
      const y = (height - (group.length - 1) * ROW_STEP) / 2 + row * ROW_STEP;
      const positionedNode: PositionedNode = {
        ...node,
        x: MAP_MARGIN_X + depth * LAYER_STEP,
        y,
        radius: depth === 0 ? 34 : depth === 1 ? 27 : depth === 2 ? 22 : 17,
      };
      positioned.push(positionedNode);
      positionByRef.set(node.ref, positionedNode);
    });
  }
  const links: OrbitLink[] = [];
  for (const node of positioned) {
    for (const childRef of node.children) {
      const child = positionByRef.get(childRef);
      if (!child) continue;
      links.push({
        key: `${node.ref}-${child.ref}`,
        from: { x: node.x + node.radius, y: node.y },
        to: { x: child.x - child.radius, y: child.y },
        type: child.type,
      });
    }
  }
  const width = Math.max(VIEW_WIDTH, MAP_MARGIN_X * 2 + 3 * LAYER_STEP + 170);
  return { nodes: positioned, links, width, height };
}

function statusLabel(progress: number): string {
  if (progress >= 100) return "Complete";
  if (progress >= 65) return "Strong progress";
  if (progress >= 30) return "In progress";
  return "Getting started";
}

export default function AtlasFocusMapPanel({
  filteredRefs,
  atlasIndex,
  atlasRoots,
  selectedRef,
  onSelectRef,
  onAddChild,
  onCreateGoal,
  nodeQuery,
  onNodeQueryChange,
  hasSnapshotPayload,
  nodeTagForType,
}: AtlasFocusMapPanelProps) {
  const [view, setView] = useState<"map" | "outline">("map");
  const [focusedBranch, setFocusedBranch] = useState(false);
  const [collapsedRefs, setCollapsedRefs] = useState<Set<string>>(() => new Set());

  const allNodes = useMemo(
    () => buildVisibleTree(filteredRefs, atlasIndex || {}, atlasRoots),
    [atlasIndex, atlasRoots, filteredRefs],
  );
  const visibleNodes = useMemo(() => {
    if (!focusedBranch || !selectedRef) return allNodes;
    const selected = atlasIndex?.[selectedRef];
    if (!selected) return allNodes;
    const keep = new Set([selectedRef, ...(selected.parent ? [selected.parent] : []), ...(selected.children || [])]);
    let parent = selected.parent;
    while (parent && atlasIndex?.[parent]) {
      keep.add(parent);
      parent = atlasIndex[parent].parent || null;
    }
    return allNodes.filter((node) => keep.has(node.ref));
  }, [allNodes, atlasIndex, focusedBranch, selectedRef]);
  const visibleRefs = useMemo(() => {
    const byRef = new Map(visibleNodes.map((node) => [node.ref, node]));
    const roots = (atlasRoots || visibleNodes.filter((node) => !node.parent).map((node) => node.ref))
      .filter((ref) => byRef.has(ref));
    const stack = [...roots].reverse().map((ref) => ({ ref, ancestorCollapsed: false }));
    const output: string[] = [];
    while (stack.length && output.length < 600) {
      const entry = stack.pop();
      if (!entry || entry.ancestorCollapsed) continue;
      const node = byRef.get(entry.ref);
      if (!node) continue;
      output.push(entry.ref);
      const ancestorCollapsed = collapsedRefs.has(entry.ref);
      for (let i = node.children.length - 1; i >= 0; i -= 1) {
        stack.push({ ref: node.children[i], ancestorCollapsed });
      }
    }
    for (const node of visibleNodes) {
      if (!output.includes(node.ref) && (!node.parent || !byRef.has(node.parent))) output.push(node.ref);
    }
    return output;
  }, [atlasRoots, collapsedRefs, visibleNodes]);
  const layoutNodes = useMemo(
    () => visibleNodes.filter((node) => visibleRefs.includes(node.ref)),
    [visibleNodes, visibleRefs],
  );
  const rootRefs = atlasRoots || allNodes.filter((node) => !node.parent).map((node) => node.ref);
  const layout = useMemo(() => makeOrbitLayout(layoutNodes, rootRefs, atlasIndex || {}), [atlasIndex, layoutNodes, rootRefs]);
  const selectedNode = allNodes.find((node) => node.ref === selectedRef) || null;
  const ancestors = useMemo(() => {
    const chain: string[] = [];
    let parent = selectedNode?.parent || null;
    while (parent && atlasIndex?.[parent]) {
      chain.unshift(parent);
      parent = atlasIndex[parent].parent || null;
    }
    return chain;
  }, [atlasIndex, selectedNode]);

  function toggleCollapsed(ref: string): void {
    setCollapsedRefs((previous) => {
      const next = new Set(previous);
      if (next.has(ref)) next.delete(ref);
      else next.add(ref);
      return next;
    });
  }

  const emptyMessage = hasSnapshotPayload ? "No matching outcomes. Try another search." : "Your strategy map will appear here once the cycle loads.";

  return (
    <div className="orbit-map" aria-label="Focus map workspace">
      <header className="orbit-map__header">
        <div className="orbit-map__title-group">
          <span className="orbit-map__eyebrow"><span className="orbit-map__signal" /> STRATEGY FIELD</span>
          <h2 className="orbit-map__title">Focus map</h2>
          <p className="orbit-map__subtitle">See how today’s work connects to the outcomes that matter.</p>
        </div>
        <div className="orbit-map__actions">
          <div className="orbit-map__view-toggle" role="group" aria-label="Map view">
            <button type="button" aria-pressed={view === "map"} onClick={() => setView("map")}>
              <span aria-hidden="true">✳</span> Map
            </button>
            <button type="button" aria-pressed={view === "outline"} onClick={() => setView("outline")}>
              <span aria-hidden="true">☷</span> Outline
            </button>
          </div>
          <button type="button" className="orbit-map__create" onClick={onCreateGoal}>
            <span aria-hidden="true">＋</span> New goal
          </button>
        </div>
      </header>

      <div className="orbit-map__toolbar">
        <label className="orbit-map__search">
          <span className="orbit-map__search-icon" aria-hidden="true">⌕</span>
          <span className="orbit-map__sr-only">Search outcomes, owners, or descriptions</span>
          <input
            value={nodeQuery}
            onChange={(event) => onNodeQueryChange(event.target.value)}
            placeholder="Find an outcome, owner, or task…"
          />
          {nodeQuery ? <button type="button" aria-label="Clear search" onClick={() => onNodeQueryChange("")}>×</button> : <kbd>⌘ K</kbd>}
        </label>
        <button
          type="button"
          className={`orbit-map__focus-toggle${focusedBranch ? " is-active" : ""}`}
          aria-pressed={focusedBranch}
          onClick={() => setFocusedBranch((value) => !value)}
          disabled={!selectedNode}
          title={selectedNode ? "Dim outcomes outside the selected path" : "Select an outcome to focus its path"}
        >
          <span aria-hidden="true">◎</span> Focus path
        </button>
      </div>

      {nodeQuery.trim() ? (
        <div className="orbit-map__search-summary" role="status">
          {filteredRefs.length} {filteredRefs.length === 1 ? "match" : "matches"}
          {filteredRefs.length ? " · related branches remain visible" : " · try a broader term"}
        </div>
      ) : null}

      {selectedNode ? (
        <nav className="orbit-map__breadcrumb" aria-label="Selected outcome path">
          {ancestors.map((ref) => (
            <span key={ref} className="orbit-map__crumb-wrap">
              <button type="button" onClick={() => onSelectRef(ref)}>{atlasIndex?.[ref]?.title || ref}</button>
              <span aria-hidden="true">/</span>
            </span>
          ))}
          <span aria-current="page">{selectedNode.title}</span>
          <span className="orbit-map__breadcrumb-status">{statusLabel(selectedNode.progress)}</span>
        </nav>
      ) : null}

      <div className="orbit-map__canvas-shell">
        {view === "map" && layout.nodes.length ? (
          <div className="orbit-map__canvas" role="region" aria-label="Strategy relationship map" tabIndex={0}>
            <div className="orbit-map__layer-labels" aria-hidden="true">
              <span>INTENT</span><span>OUTCOMES</span><span>MEASURES</span><span>WORK</span>
            </div>
            <svg
              className="orbit-map__svg"
              viewBox={`0 0 ${layout.width} ${layout.height}`}
              role="img"
              aria-label={`Map with ${layout.nodes.length} outcomes and ${layout.links.length} connections`}
              preserveAspectRatio="xMinYMin meet"
            >
              <defs>
                <linearGradient id="orbit-link-gradient" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#7357f2" stopOpacity=".34" />
                  <stop offset="100%" stopColor="#36b8a0" stopOpacity=".28" />
                </linearGradient>
                <pattern id="orbit-dot-grid" width="24" height="24" patternUnits="userSpaceOnUse">
                  <circle cx="1" cy="1" r="1" fill="currentColor" opacity=".13" />
                </pattern>
              </defs>
              <rect className="orbit-map__grid" width={layout.width} height={layout.height} fill="url(#orbit-dot-grid)" />
              {layout.links.map((link) => {
                const highlighted = !selectedRef || link.key.includes(selectedRef) || ancestors.some((ref) => link.key.includes(ref));
                return (
                  <path
                    key={link.key}
                    className={`orbit-map__link orbit-map__link--${link.type.toLowerCase()}${highlighted ? " is-highlighted" : ""}`}
                    d={`M ${link.from.x} ${link.from.y} C ${link.from.x + 58} ${link.from.y}, ${link.to.x - 58} ${link.to.y}, ${link.to.x} ${link.to.y}`}
                  />
                );
              })}
              {layout.nodes.map((node) => {
                const selected = selectedRef === node.ref;
                const related = !selectedRef || selected || ancestors.includes(node.ref) || node.parent === selectedRef;
                const isCollapsed = collapsedRefs.has(node.ref);
                const tag = nodeTagForType(node.type);
                return (
                  <g
                    key={node.ref}
                    className={`orbit-map__node orbit-map__node--${node.type.toLowerCase()}${selected ? " is-selected" : ""}${related ? " is-related" : " is-muted"}`}
                    transform={`translate(${node.x} ${node.y})`}
                  >
                    <circle className="orbit-map__halo" r={node.radius + 10} />
                    <circle className="orbit-map__progress-track" r={node.radius} />
                    <circle
                      className="orbit-map__progress-value"
                      r={node.radius}
                      pathLength="100"
                      strokeDasharray={`${node.progress} ${100 - node.progress}`}
                      transform="rotate(-90)"
                    />
                    <foreignObject x={-node.radius + 5} y={-node.radius + 5} width={(node.radius - 5) * 2} height={(node.radius - 5) * 2}>
                      <button
                        type="button"
                        className="orbit-map__node-core"
                        aria-label={`${TYPE_LABEL[node.type] || node.type}: ${node.title}, ${node.progress}% complete${node.ownerName ? `, owner ${node.ownerName}` : ""}`}
                        aria-pressed={selected}
                        onClick={() => onSelectRef(node.ref)}
                        onKeyDown={(event) => {
                          if (event.key === "ArrowRight" && node.children.length) {
                            event.preventDefault();
                            const child = layout.nodes.find((item) => item.ref === node.children[0]);
                            child && document.getElementById(`orbit-node-${child.ref}`)?.focus();
                          }
                          if (event.key === "ArrowLeft" && node.parent) {
                            event.preventDefault();
                            document.getElementById(`orbit-node-${node.parent}`)?.focus();
                          }
                        }}
                        id={`orbit-node-${node.ref}`}
                        title={`${tag} · ${node.title} · ${node.progress}%`}
                      >
                        <span>{tag}</span>
                      </button>
                    </foreignObject>
                    <foreignObject x={node.radius + 12} y={-30} width={190} height={62}>
                      <button
                        type="button"
                        className="orbit-map__node-label"
                        aria-label={`Select ${TYPE_LABEL[node.type] || node.type}: ${node.title}`}
                        aria-pressed={selected}
                        onClick={() => onSelectRef(node.ref)}
                      >
                        <span className="orbit-map__node-type">{TYPE_LABEL[node.type] || node.type}</span>
                        <span className="orbit-map__node-title">{node.title}</span>
                        {node.ownerName && node.ownerName !== "Unknown" ? <span className="orbit-map__node-owner">{node.ownerName}</span> : null}
                      </button>
                    </foreignObject>
                    {node.children.length ? (
                      <foreignObject x={-10} y={node.radius - 1} width={20} height={20}>
                        <button
                          type="button"
                          className="orbit-map__collapse"
                          aria-label={`${isCollapsed ? "Expand" : "Collapse"} ${node.title}`}
                          aria-expanded={!isCollapsed}
                          onClick={() => toggleCollapsed(node.ref)}
                        >{isCollapsed ? "+" : "−"}</button>
                      </foreignObject>
                    ) : null}
                  </g>
                );
              })}
            </svg>
            <div className="orbit-map__legend" aria-label="Progress status legend">
              <span><i className="orbit-map__legend-dot is-started" />Early</span>
              <span><i className="orbit-map__legend-dot is-moving" />Moving</span>
              <span><i className="orbit-map__legend-dot is-strong" />Strong</span>
              <span><i className="orbit-map__legend-dot is-done" />Complete</span>
            </div>
            {selectedNode ? (
              <aside className="orbit-map__selection-card" aria-live="polite">
                <div className="orbit-map__selection-topline"><span>{TYPE_LABEL[selectedNode.type] || selectedNode.type}</span><span>{selectedNode.progress}%</span></div>
                <strong>{selectedNode.title}</strong>
                <span>{statusLabel(selectedNode.progress)}{selectedNode.ownerName && selectedNode.ownerName !== "Unknown" ? ` · ${selectedNode.ownerName}` : ""}</span>
                {selectedNode.type !== "TASK" ? <button type="button" onClick={() => onAddChild(selectedNode.ref)}>＋ Add {selectedNode.type === "GOAL" ? "objective" : selectedNode.type === "OBJECTIVE" ? "key result" : "task"}</button> : null}
              </aside>
            ) : null}
          </div>
        ) : view === "map" ? (
          <div className="orbit-map__empty"><span aria-hidden="true">✳</span><p>{emptyMessage}</p><button type="button" onClick={onCreateGoal}>Create your first goal</button></div>
        ) : null}

        {view === "outline" ? (
          <div className="orbit-map__outline" role="tree" aria-label="Strategy outline">
            {visibleRefs.map((ref) => {
              const node = allNodes.find((item) => item.ref === ref);
              if (!node) return null;
              const childrenVisible = node.children.some((child) => visibleRefs.includes(child));
              const collapsed = collapsedRefs.has(ref);
              return (
                <div key={ref} className={`orbit-map__outline-row orbit-map__outline-row--${node.type.toLowerCase()}`} role="treeitem" aria-level={node.depth + 1} aria-selected={selectedRef === ref}>
                  <span className="orbit-map__outline-indent" style={{ width: `${Math.min(node.depth, 5) * 1.1}rem` }} />
                  {node.children.length ? <button type="button" aria-label={`${collapsed ? "Expand" : "Collapse"} ${node.title}`} aria-expanded={!collapsed} onClick={() => toggleCollapsed(ref)}>{collapsed ? "+" : "−"}</button> : <span className="orbit-map__outline-spacer" />}
                  <button type="button" className="orbit-map__outline-select" aria-label={`Select ${node.title}`} aria-pressed={selectedRef === ref} onClick={() => onSelectRef(ref)}>
                    <span className="orbit-map__outline-tag" aria-hidden="true">{nodeTagForType(node.type)}</span><span>{node.title}</span>
                  </button>
                  <span className="orbit-map__outline-progress">{node.progress}%</span>
                  {node.type !== "TASK" ? <button type="button" className="orbit-map__outline-add" aria-label={`Add child to ${node.title}`} onClick={() => onAddChild(ref)}>＋</button> : null}
                  {childrenVisible && !collapsed ? <span className="orbit-map__sr-only">Has visible children</span> : null}
                </div>
              );
            })}
            {!visibleRefs.length ? <p className="orbit-map__empty-copy">{emptyMessage}</p> : null}
          </div>
        ) : null}
      </div>

      <footer className="orbit-map__footer">
        <div className="orbit-map__footer-stats"><span><strong>{allNodes.filter((node) => node.type === "GOAL").length}</strong> goals</span><i /> <span><strong>{allNodes.filter((node) => node.type === "OBJECTIVE").length}</strong> objectives</span><i /> <span><strong>{allNodes.filter((node) => node.type === "KEY_RESULT").length}</strong> measures</span><i /> <span><strong>{allNodes.filter((node) => node.type === "TASK").length}</strong> actions</span></div>
        <span className="orbit-map__footer-hint"><kbd>←</kbd><kbd>→</kbd> Move through the strategy</span>
      </footer>
    </div>
  );
}
