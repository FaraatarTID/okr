import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import * as React from "react";

import useSelectionFocusSync from "@/components/atlas-shell/useSelectionFocusSync";

type HarnessProps = {
  atlasRuntime: { roots: string[]; index: Record<string, unknown> } | null;
  selectedRef: string;
  taskRefs: string[];
  focusTaskRef: string;
  selectedMeta: { type: string; ref: string } | null;
  cycleId: string;
  createDraft: { cycleId: string; title: string };
};

function renderSyncHook(initialProps: HarnessProps) {
  return renderHook((props: HarnessProps) => {
    const [selectedRef, setSelectedRef] = React.useState(props.selectedRef);
    const [focusTaskRef, setFocusTaskRef] = React.useState(props.focusTaskRef);
    const [createDraft, setCreateDraft] = React.useState(props.createDraft);

    useSelectionFocusSync({
      atlasRuntime: props.atlasRuntime,
      selectedRef,
      setSelectedRef,
      taskRefs: props.taskRefs,
      focusTaskRef,
      setFocusTaskRef,
      selectedMeta: props.selectedMeta,
      cycleId: props.cycleId,
      setCreateDraft,
    });

    return {
      selectedRef,
      focusTaskRef,
      createDraft,
    };
  }, { initialProps });
}

describe("useSelectionFocusSync", () => {
  it("defaults selection to first root when current ref is missing", async () => {
    const { result } = renderSyncHook({
      atlasRuntime: { roots: ["goal_1"], index: { goal_1: {} } },
      selectedRef: "",
      taskRefs: [],
      focusTaskRef: "",
      selectedMeta: null,
      cycleId: "3",
      createDraft: { cycleId: "", title: "draft" },
    });

    await waitFor(() => {
      expect(result.current.selectedRef).toBe("goal_1");
      expect(result.current.createDraft.cycleId).toBe("3");
    });
  });

  it("clears selection when atlas runtime has no roots", async () => {
    const { result } = renderSyncHook({
      atlasRuntime: null,
      selectedRef: "goal_1",
      taskRefs: [],
      focusTaskRef: "",
      selectedMeta: null,
      cycleId: "3",
      createDraft: { cycleId: "3", title: "draft" },
    });

    await waitFor(() => {
      expect(result.current.selectedRef).toBe("");
    });
  });

  it("clears invalid focus task refs", async () => {
    const { result } = renderSyncHook({
      atlasRuntime: { roots: ["goal_1"], index: { goal_1: {} } },
      selectedRef: "goal_1",
      taskRefs: ["task_2"],
      focusTaskRef: "task_1",
      selectedMeta: null,
      cycleId: "5",
      createDraft: { cycleId: "5", title: "draft" },
    });

    await waitFor(() => {
      expect(result.current.focusTaskRef).toBe("");
    });
  });

  it("syncs focus to selected task ref", async () => {
    const { result } = renderSyncHook({
      atlasRuntime: { roots: ["task_9"], index: { task_9: {} } },
      selectedRef: "task_9",
      taskRefs: ["task_9"],
      focusTaskRef: "",
      selectedMeta: { type: "TASK", ref: "task_9" },
      cycleId: "5",
      createDraft: { cycleId: "5", title: "draft" },
    });

    await waitFor(() => {
      expect(result.current.focusTaskRef).toBe("task_9");
    });
  });

  it("does not override existing create draft cycle id", async () => {
    const { result } = renderSyncHook({
      atlasRuntime: { roots: ["goal_1"], index: { goal_1: {} } },
      selectedRef: "goal_1",
      taskRefs: [],
      focusTaskRef: "",
      selectedMeta: null,
      cycleId: "22",
      createDraft: { cycleId: "11", title: "draft" },
    });

    await waitFor(() => {
      expect(result.current.createDraft.cycleId).toBe("11");
    });
  });
});
