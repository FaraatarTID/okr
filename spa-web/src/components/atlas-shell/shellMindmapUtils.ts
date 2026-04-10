import { nodeTypeLabel, type AtlasIndexNode } from "@/lib/atlas";

export type MindmapTreeNode = {
  id: number | null;
  type: "GOAL" | "OBJECTIVE" | "KEY_RESULT" | "TASK" | "NODE";
  title: string;
  progress: number | null;
  children: MindmapTreeNode[];
};

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function parseNumberOrNull(value: unknown): number | null {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

export function normalizedMindmapType(raw: unknown): MindmapTreeNode["type"] {
  const text = String(raw || "").trim().toUpperCase();
  if (text === "GOAL" || text === "OBJECTIVE" || text === "KEY_RESULT" || text === "TASK") {
    return text;
  }
  return "NODE";
}

export function inferChildType(parentType: MindmapTreeNode["type"]): MindmapTreeNode["type"] {
  if (parentType === "GOAL") {
    return "OBJECTIVE";
  }
  if (parentType === "OBJECTIVE") {
    return "KEY_RESULT";
  }
  if (parentType === "KEY_RESULT") {
    return "TASK";
  }
  return "NODE";
}

export function buildMindmapTree(nodeRaw: unknown, nodeTypeRaw?: unknown): MindmapTreeNode | null {
  const node = asRecord(nodeRaw);
  if (!node) {
    return null;
  }
  const type = normalizedMindmapType(node.__tablename__ || nodeTypeRaw || node.node_type || node.type);
  const idRaw = Number(node.id);
  const id = Number.isFinite(idRaw) ? idRaw : null;
  const title = String(node.title || `${type}${id ? ` #${id}` : ""}` || "Node").trim();
  const progress = parseNumberOrNull(node.progress);
  const childType = inferChildType(type);
  const childrenRaw =
    (Array.isArray(node.objectives) ? node.objectives : null) ||
    (Array.isArray(node.key_results) ? node.key_results : null) ||
    (Array.isArray(node.tasks) ? node.tasks : null) ||
    [];
  const children = childrenRaw
    .map((item) => buildMindmapTree(item, childType))
    .filter((item): item is MindmapTreeNode => Boolean(item));
  return {
    id,
    type,
    title,
    progress,
    children,
  };
}

export function isGenericIndexedTitle(
  title: string,
  nodeType: AtlasIndexNode["type"],
  nodeId: number,
): boolean {
  const normalized = String(title || "").trim().toLowerCase();
  if (!normalized) {
    return true;
  }
  const safeId = Number(nodeId);
  if (!Number.isFinite(safeId) || safeId <= 0) {
    return false;
  }
  const typeToken = nodeType.replace(/_/g, " ").toLowerCase();
  const labelToken = nodeTypeLabel(nodeType).toLowerCase();
  const id = Math.round(safeId);
  const fallbackTokens = new Set([
    `${typeToken} #${id}`,
    `${typeToken} ${id}`,
    `${typeToken}#${id}`,
    `${labelToken} #${id}`,
    `${labelToken} ${id}`,
    `${labelToken}#${id}`,
  ]);
  return fallbackTokens.has(normalized);
}

export function findMindmapNodeTitle(
  root: MindmapTreeNode | null,
  nodeType: AtlasIndexNode["type"],
  nodeId: number,
): string {
  if (!root) {
    return "";
  }
  const stack: MindmapTreeNode[] = [root];
  while (stack.length) {
    const current = stack.pop();
    if (!current) {
      continue;
    }
    if (current.type === nodeType && current.id === nodeId) {
      return String(current.title || "").trim();
    }
    for (const child of current.children) {
      stack.push(child);
    }
  }
  return "";
}
