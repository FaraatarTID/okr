import React from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import InspectorManageNodesPanel from "@/components/atlas-shell/InspectorManageNodesPanel";

function createTypeLabel(createType: "goal" | "objective" | "key_result" | "task"): string {
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

describe("InspectorManageNodesPanel", () => {
  it("renders goal-specific fields and emits draft/create callbacks", async () => {
    const user = userEvent.setup();
    const onCreateDraftChange = vi.fn();
    const onCreateNode = vi.fn();

    render(
      <InspectorManageNodesPanel
        createDraft={{
          createType: "goal",
          title: "Q3 goal",
          description: "desc",
          cycleId: "7",
          tags: "growth",
          targetValue: "100",
          unit: "%",
          estimatedMinutes: "30",
          assigneeId: "",
        }}
        onCreateDraftChange={onCreateDraftChange}
        createContext={{ goalId: null, objectiveId: null, keyResultId: null }}
        canCreateForContext
        createTypeLabel={createTypeLabel}
        cycleLabel="Q3-2026"
        onCreateNode={onCreateNode}
        createPending={false}
        hasUser

        createError=""
        createMessage=""
        deleteError=""
        deleteMessage=""
      />,
    );

    expect(screen.getByText("Cycle: Q3-2026")).toBeInTheDocument();
    expect(screen.getByLabelText("Strategy Tags (optional, comma-separated)")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Goal Title"), { target: { value: "New goal" } });
    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "New desc" } });
    fireEvent.change(screen.getByLabelText("Strategy Tags (optional, comma-separated)"), {
      target: { value: "a,b" },
    });

    expect(onCreateDraftChange).toHaveBeenCalledWith({ title: "New goal" });
    expect(onCreateDraftChange).toHaveBeenCalledWith({ description: "New desc" });
    expect(onCreateDraftChange).toHaveBeenCalledWith({ tags: "a,b" });

    await user.click(screen.getByRole("button", { name: "Create Goal" }));
    expect(onCreateNode).toHaveBeenCalledTimes(1);
  });

  it("renders key-result fields and context references", () => {
    render(
      <InspectorManageNodesPanel
        createDraft={{
          createType: "key_result",
          title: "KR",
          description: "desc",
          cycleId: "7",
          tags: "initiative",
          targetValue: "55",
          unit: "%",
          estimatedMinutes: "30",
          assigneeId: "",
        }}
        onCreateDraftChange={vi.fn()}
        createContext={{ goalId: 1, objectiveId: 22, keyResultId: null }}
        canCreateForContext
        createTypeLabel={createTypeLabel}
        cycleLabel="Q3-2026"
        onCreateNode={vi.fn()}
        createPending={false}
        hasUser

        createError="create error"
        createMessage="create ok"
        deleteError="delete error"
        deleteMessage="delete ok"
      />,
    );

    expect(screen.getByText("Parent Objective ID: 22")).toBeInTheDocument();
    expect(screen.getByLabelText("Target Value")).toBeInTheDocument();
    expect(screen.getByLabelText("Unit")).toBeInTheDocument();
    expect(screen.getByLabelText("Initiative Tags (optional, comma-separated)")).toBeInTheDocument();
    expect(screen.getByText("create error")).toBeInTheDocument();
    expect(screen.getByText("create ok")).toBeInTheDocument();
    expect(screen.getByText("delete error")).toBeInTheDocument();
    expect(screen.getByText("delete ok")).toBeInTheDocument();
  });

  it("shows invalid-context warning and disables create action for task mode", () => {
    render(
      <InspectorManageNodesPanel
        createDraft={{
          createType: "task",
          title: "Task",
          description: "desc",
          cycleId: "7",
          tags: "",
          targetValue: "100",
          unit: "%",
          estimatedMinutes: "25",
          assigneeId: "9",
        }}
        onCreateDraftChange={vi.fn()}
        createContext={{ goalId: 1, objectiveId: 2, keyResultId: null }}
        canCreateForContext={false}
        createTypeLabel={createTypeLabel}
        cycleLabel="Q3-2026"
        onCreateNode={vi.fn()}
        createPending={false}
        hasUser

        createError=""
        createMessage=""
        deleteError=""
        deleteMessage=""
      />,
    );

    expect(screen.getByText("Parent Key Result ID: -")).toBeInTheDocument();
    expect(screen.getByLabelText("Estimated Minutes")).toBeInTheDocument();
    expect(screen.getByLabelText("Assignee ID (optional)")).toBeInTheDocument();
    expect(
      screen.getByText("Current selection does not provide a valid parent for this create type."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create Task" })).toBeDisabled();
  });
});
