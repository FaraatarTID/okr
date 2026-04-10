"use client";

import type { AtlasIndexNode } from "@/lib/atlas";
import type { NodeTypePath } from "@/lib/api";

export function nodeTypeToPath(nodeType: AtlasIndexNode["type"]): NodeTypePath {
  if (nodeType === "GOAL") {
    return "goal";
  }
  if (nodeType === "OBJECTIVE") {
    return "objective";
  }
  if (nodeType === "KEY_RESULT") {
    return "key_result";
  }
  return "task";
}

export function mutationNodeRef(nodeType: AtlasIndexNode["type"], nodeId: number): string {
  const typePrefix = nodeType === "KEY_RESULT" ? "key_result" : nodeType.toLowerCase();
  return `${typePrefix}_${nodeId}`;
}

export function createTypeLabel(createType: NodeTypePath): string {
  if (createType === "goal") {
    return "Goal";
  }
  if (createType === "objective") {
    return "Objective";
  }
  if (createType === "key_result") {
    return "Key Result";
  }
  return "Task";
}

export function nearestAncestorId(
  meta: AtlasIndexNode | null,
  index: Record<string, AtlasIndexNode> | null,
  nodeType: AtlasIndexNode["type"],
): number | null {
  if (!meta || !index) {
    return null;
  }
  for (let idx = meta.path.length - 1; idx >= 0; idx -= 1) {
    const candidate = index[meta.path[idx]];
    if (candidate && candidate.type === nodeType) {
      return candidate.id;
    }
  }
  return null;
}
