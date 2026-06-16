export type AtlasNodeType = "GOAL" | "OBJECTIVE" | "KEY_RESULT" | "TASK";

export interface AtlasTaskSnapshot {
  id: number;
  title: string;
  description: string;
  progress: number;
  deadline: string | null;
  timer_started_at: string | null;
  status: string;
  total_time_spent: number;
  estimated_minutes: number;
  assignee_id: number | null;
}

export interface AtlasKeyResultSnapshot {
  id: number;
  title: string;
  description: string;
  progress: number;
  ai_overall_score?: number | null;
  ai_deadline_state?: string | null;
  start_value?: number | null;
  target_value?: number | null;
  current_value?: number | null;
  metric_type?: string | null;
  weight?: number | null;
  unit?: string | null;
  ai_analysis?: string | null;
  analysis_updated_at?: string | null;
  tasks: AtlasTaskSnapshot[];
}

export interface AtlasObjectiveSnapshot {
  id: number;
  title: string;
  description: string;
  progress: number;
  score_mode?: string | null;
  weight?: number | null;
  key_results: AtlasKeyResultSnapshot[];
}

export interface AtlasGoalSnapshot {
  id: number;
  title: string;
  description: string;
  progress: number;
  owner_id: number;
  objectives: AtlasObjectiveSnapshot[];
}

export interface AtlasSnapshotResponse {
  goals: AtlasGoalSnapshot[];
  users_map: Record<string, string>;
}

export type AtlasNodePayload =
  | AtlasGoalSnapshot
  | AtlasObjectiveSnapshot
  | AtlasKeyResultSnapshot
  | AtlasTaskSnapshot;

export interface AtlasIndexNode {
  ref: string;
  id: number;
  node: AtlasNodePayload;
  type: AtlasNodeType;
  title: string;
  titleLower: string;
  description: string;
  progress: number;
  depth: number;
  parent: string | null;
  path: string[];
  children: string[];
  ownerId: number | null;
  nodeOwnerId: number | null;
  timerOwnerId: number | null;
  ownerName: string;
}

function typedRefForTypeAndId(nodeType: AtlasNodeType, nodeId: number | null | undefined): string | null {
  if (!Number.isInteger(nodeId) || Number(nodeId) <= 0) {
    return null;
  }
  return `${nodeType.toLowerCase()}_${nodeId}`;
}

export function parseTypedRef(value: string | null | undefined): {
  nodeType: AtlasNodeType | null;
  nodeId: number | null;
} {
  const raw = String(value || "").trim().toLowerCase();
  const matched = raw.match(/^(goal|objective|key_result|task)_([1-9]\d*)$/);
  if (!matched) {
    return { nodeType: null, nodeId: null };
  }
  const mappedType = matched[1] === "key_result" ? "KEY_RESULT" : matched[1].toUpperCase();
  const nodeType = mappedType as AtlasNodeType;
  return {
    nodeType,
    nodeId: Number.parseInt(matched[2], 10),
  };
}

function ownerNameFromMap(usersMap: Record<string, string>, ownerId: number | null): string {
  if (!Number.isInteger(ownerId) || Number(ownerId) <= 0) {
    return "Unknown";
  }
  const key = String(ownerId);
  return String(usersMap[key] || "").trim() || "Unknown";
}

function asSafeText(value: unknown): string {
  return String(value || "").trim();
}

function asSafeProgress(value: unknown): number {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return 0;
  }
  const rounded = Math.round(numeric);
  if (rounded < 0) {
    return 0;
  }
  if (rounded > 100) {
    return 100;
  }
  return rounded;
}

export function buildAtlasIndexFromSnapshot(snapshot: AtlasSnapshotResponse): {
  index: Record<string, AtlasIndexNode>;
  roots: string[];
} {
  const index: Record<string, AtlasIndexNode> = {};
  const roots: string[] = [];
  const usersMap = snapshot.users_map || {};

  function visit(
    nodeType: AtlasNodeType,
    payload: AtlasNodePayload,
    parentRef: string | null,
    path: string[],
    timerOwnerId: number | null,
  ): void {
    const nodeRef = typedRefForTypeAndId(nodeType, Number(payload.id));
    if (!nodeRef) {
      return;
    }

    const title = asSafeText(payload.title) || "Untitled";
    const description = asSafeText(payload.description);
    const progress = asSafeProgress(payload.progress);
    const nodeOwnerId =
      "owner_id" in payload && Number.isInteger(payload.owner_id)
        ? Number(payload.owner_id)
        : null;
    const resolvedTimerOwner = timerOwnerId ?? nodeOwnerId;

    let childType: AtlasNodeType | null = null;
    let childrenPayload: AtlasNodePayload[] = [];

    if (nodeType === "GOAL") {
      const goalPayload = payload as AtlasGoalSnapshot;
      childType = "OBJECTIVE";
      childrenPayload = [...(goalPayload.objectives || [])];
    } else if (nodeType === "OBJECTIVE") {
      const objectivePayload = payload as AtlasObjectiveSnapshot;
      childType = "KEY_RESULT";
      childrenPayload = [...(objectivePayload.key_results || [])];
    } else if (nodeType === "KEY_RESULT") {
      const keyResultPayload = payload as AtlasKeyResultSnapshot;
      childType = "TASK";
      childrenPayload = [...(keyResultPayload.tasks || [])];
    }

    const childRefs: string[] = [];
    if (childType) {
      for (const child of childrenPayload) {
        const childRef = typedRefForTypeAndId(childType, Number(child.id));
        if (childRef) {
          childRefs.push(childRef);
        }
      }
    }

    const nextPath = [...path, nodeRef];
    index[nodeRef] = {
      ref: nodeRef,
      id: Number(payload.id),
      node: payload,
      type: nodeType,
      title,
      titleLower: title.toLowerCase(),
      description,
      progress,
      depth: nextPath.length - 1,
      parent: parentRef,
      path: nextPath,
      children: childRefs,
      ownerId: resolvedTimerOwner,
      nodeOwnerId,
      timerOwnerId: resolvedTimerOwner,
      ownerName: ownerNameFromMap(usersMap, resolvedTimerOwner),
    };

    if (childType) {
      for (const child of childrenPayload) {
        visit(childType, child, nodeRef, nextPath, resolvedTimerOwner);
      }
    }
  }

  for (const goal of snapshot.goals || []) {
    const rootRef = typedRefForTypeAndId("GOAL", Number(goal.id));
    if (!rootRef) {
      continue;
    }
    roots.push(rootRef);
    visit("GOAL", goal, null, [], Number(goal.owner_id));
  }

  return { index, roots };
}

export function flattenScopeRefs(
  roots: string[],
  index: Record<string, AtlasIndexNode>,
  limit = 5_000,
): string[] {
  const output: string[] = [];
  const stack = [...roots].reverse();
  const seen = new Set<string>();

  while (stack.length > 0 && output.length < limit) {
    const ref = stack.pop();
    if (!ref || seen.has(ref)) {
      continue;
    }
    seen.add(ref);
    output.push(ref);

    const children = index[ref]?.children || [];
    for (let idx = children.length - 1; idx >= 0; idx -= 1) {
      stack.push(children[idx]);
    }
  }

  return output;
}

export function nodeTypeLabel(nodeType: AtlasNodeType): string {
  if (nodeType === "GOAL") {
    return "Goal";
  }
  if (nodeType === "OBJECTIVE") {
    return "Objective";
  }
  if (nodeType === "KEY_RESULT") {
    return "Key Result";
  }
  return "Task";
}

export function atlasRollup(index: Record<string, AtlasIndexNode>): {
  goals: number;
  objectives: number;
  keyResults: number;
  tasks: number;
} {
  let goals = 0;
  let objectives = 0;
  let keyResults = 0;
  let tasks = 0;

  for (const meta of Object.values(index)) {
    if (meta.type === "GOAL") {
      goals += 1;
    } else if (meta.type === "OBJECTIVE") {
      objectives += 1;
    } else if (meta.type === "KEY_RESULT") {
      keyResults += 1;
    } else if (meta.type === "TASK") {
      tasks += 1;
    }
  }

  return {
    goals,
    objectives,
    keyResults,
    tasks,
  };
}
