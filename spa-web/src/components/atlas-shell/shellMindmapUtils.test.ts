import { describe, expect, it } from "vitest";

import {
  buildMindmapTree,
  findMindmapNodeTitle,
  inferChildType,
  isGenericIndexedTitle,
  normalizedMindmapType,
} from "@/components/atlas-shell/shellMindmapUtils";

describe("shellMindmapUtils", () => {
  it("normalizes node types and infers child hierarchy", () => {
    expect(normalizedMindmapType("goal")).toBe("GOAL");
    expect(normalizedMindmapType("unknown")).toBe("NODE");
    expect(inferChildType("GOAL")).toBe("OBJECTIVE");
    expect(inferChildType("OBJECTIVE")).toBe("KEY_RESULT");
    expect(inferChildType("KEY_RESULT")).toBe("TASK");
    expect(inferChildType("NODE")).toBe("NODE");
  });

  it("builds a nested mindmap tree from backend payload", () => {
    const tree = buildMindmapTree({
      id: 1,
      __tablename__: "goal",
      title: "Ship stabilization",
      progress: 45,
      objectives: [
        {
          id: 11,
          title: "Secure auth boundary",
          progress: 60,
          key_results: [
            {
              id: 111,
              title: "Reject forged actor",
              progress: 80,
              tasks: [{ id: 1111, title: "Add server-side actor derivation", progress: 100 }],
            },
          ],
        },
      ],
    });

    expect(tree?.type).toBe("GOAL");
    expect(tree?.children[0].type).toBe("OBJECTIVE");
    expect(tree?.children[0].children[0].type).toBe("KEY_RESULT");
    expect(tree?.children[0].children[0].children[0].type).toBe("TASK");
    expect(tree?.children[0].children[0].children[0].title).toBe("Add server-side actor derivation");
  });

  it("applies inferred type and fallback title for sparse payloads", () => {
    const inferred = buildMindmapTree({ id: 9, progress: "27" }, "OBJECTIVE");
    expect(inferred?.type).toBe("OBJECTIVE");
    expect(inferred?.title).toBe("OBJECTIVE #9");
    expect(inferred?.progress).toBe(27);

    expect(buildMindmapTree(null)).toBeNull();
  });

  it("detects generic indexed titles", () => {
    expect(isGenericIndexedTitle("goal #7", "GOAL", 7)).toBe(true);
    expect(isGenericIndexedTitle("key result 12", "KEY_RESULT", 12)).toBe(true);
    expect(isGenericIndexedTitle("Stabilize auth pipeline", "KEY_RESULT", 12)).toBe(false);
    expect(isGenericIndexedTitle("", "TASK", 4)).toBe(true);
  });

  it("finds nested node titles by type/id", () => {
    const root = buildMindmapTree({
      id: 1,
      __tablename__: "goal",
      title: "Goal A",
      objectives: [
        {
          id: 2,
          title: "Objective B",
          key_results: [
            {
              id: 3,
              title: "KR C",
              tasks: [{ id: 4, title: "Task D" }],
            },
          ],
        },
      ],
    });

    expect(findMindmapNodeTitle(root, "GOAL", 1)).toBe("Goal A");
    expect(findMindmapNodeTitle(root, "OBJECTIVE", 2)).toBe("Objective B");
    expect(findMindmapNodeTitle(root, "TASK", 4)).toBe("Task D");
    expect(findMindmapNodeTitle(root, "TASK", 99)).toBe("");
    expect(findMindmapNodeTitle(null, "TASK", 4)).toBe("");
  });
});
