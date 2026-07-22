import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import InspectorAlignmentPanel from "@/components/atlas-shell/InspectorAlignmentPanel";
import InspectorTaskWorkHistoryPanel from "@/components/atlas-shell/InspectorTaskWorkHistoryPanel";

describe("InspectorTaskWorkHistoryPanel", () => {
  it("renders work log rows and invokes delete callback", async () => {
    const user = userEvent.setup();
    const onDeleteWorkLog = vi.fn();
    const summary = "Task summary ".repeat(20);
    const preview = `${summary.slice(0, 117).trimEnd()}...`;

    render(
      <InspectorTaskWorkHistoryPanel
        inspectTaskWorkLogsPending={false}
        inspectTaskWorkLogsError=""
        inspectTaskWorkLogsActionError=""
        inspectTaskWorkLogsActionMessage=""
        inspectTaskWorkHistoryRows={[
          {
            id: 42,
            end_time: "2026-02-27T12:00:00Z",
            duration_minutes: 15.25,
            summary,
          },
        ]}
        inspectTaskWorkLogPendingId={null}
        hasUser

        formatOptionalDate={(value) => String(value || "")}
        onDeleteWorkLog={onDeleteWorkLog}
      />,
    );

    expect(screen.getByText("Work History")).toBeInTheDocument();
    expect(
      screen.getByText(
        (_, element) =>
          element?.tagName.toLowerCase() === "summary" &&
          (element.textContent?.includes(preview) ?? false),
      ),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Delete" }));
    expect(onDeleteWorkLog).toHaveBeenCalledWith(42);
  });

  it("shows deleting state and empty-state copy", () => {
    const onDeleteWorkLog = vi.fn();

    const { rerender } = render(
      <InspectorTaskWorkHistoryPanel
        inspectTaskWorkLogsPending={false}
        inspectTaskWorkLogsError=""
        inspectTaskWorkLogsActionError=""
        inspectTaskWorkLogsActionMessage=""
        inspectTaskWorkHistoryRows={[]}
        inspectTaskWorkLogPendingId={null}
        hasUser

        formatOptionalDate={(value) => String(value || "")}
        onDeleteWorkLog={onDeleteWorkLog}
      />,
    );

    expect(screen.getByText("No work logs found for this task.")).toBeInTheDocument();

    rerender(
      <InspectorTaskWorkHistoryPanel
        inspectTaskWorkLogsPending={false}
        inspectTaskWorkLogsError=""
        inspectTaskWorkLogsActionError=""
        inspectTaskWorkLogsActionMessage=""
        inspectTaskWorkHistoryRows={[{ id: 10, summary: "Row", duration_minutes: 2 }]}
        inspectTaskWorkLogPendingId={10}
        hasUser

        formatOptionalDate={(value) => String(value || "")}
        onDeleteWorkLog={onDeleteWorkLog}
      />,
    );

    expect(screen.getByRole("button", { name: "Deleting..." })).toBeDisabled();
  });
});

describe("InspectorAlignmentPanel", () => {
  it("invokes callbacks for direction, target, add, and remove actions", async () => {
    const user = userEvent.setup();
    const onDirectionChange = vi.fn();
    const onTargetChange = vi.fn();
    const onCreate = vi.fn();
    const onDelete = vi.fn();
    const onObjLinkDirectionChange = vi.fn();
    const onObjLinkTargetIdChange = vi.fn();
    const onObjLinkCreate = vi.fn();
    const onObjLinkDelete = vi.fn();

    render(
      <InspectorAlignmentPanel
        alignmentPending={false}
        alignmentError=""
        alignmentContext={{
          parents: [{ id: 1, title: "Parent Objective" }],
          children: [{ id: 2, title: "Child A" }, { id: 3, title: "Child B" }],
          all_objectives: [{ id: 5, title: "Objective 5" }],
          edges: [{ id: 77, parent_id: 1, child_id: 2, alignment_type: "SUPPORTS" }],
          available_goals: [{ id: 10, title: "Goal 10" }],
          available_key_results: [{ id: 20, title: "KR 20" }],
          objective_links: [],
        }}
        alignmentDirection="parent"
        alignmentTargetObjectiveId=""
        alignmentType="SUPPORTS"
        onAlignmentDirectionChange={onDirectionChange}
        onAlignmentTargetObjectiveIdChange={onTargetChange}
        onAlignmentTypeChange={vi.fn()}
        onAlignmentCreate={onCreate}
        onAlignmentDelete={onDelete}
        objLinkDirection="parent"
        objLinkTargetId=""
        objLinkPending={false}
        objLinkError=""
        onObjLinkDirectionChange={onObjLinkDirectionChange}
        onObjLinkTargetIdChange={onObjLinkTargetIdChange}
        onObjLinkCreate={onObjLinkCreate}
        onObjLinkDelete={onObjLinkDelete}
      />,
    );

    expect(screen.getByText("Parents: 1 | Children: 2")).toBeInTheDocument();
    const selects = screen.getAllByRole("combobox");
    // selects[0] = cross-hierarchy direction, selects[1] = cross-hierarchy target
    // selects[2] = objective-to-objective target, selects[3] = alignment type
    await user.selectOptions(selects[2], "5");
    const addButtons = screen.getAllByRole("button", { name: "Add link" });
    await user.click(addButtons[1]);
    const removeButtons = screen.getAllByRole("button", { name: "Remove" });
    await user.click(removeButtons[0]);

    expect(onTargetChange).toHaveBeenCalledWith("5");
    expect(onCreate).toHaveBeenCalledTimes(1);
    expect(onDelete).toHaveBeenCalledWith(77);
  });
});
