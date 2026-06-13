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

    render(
      <InspectorAlignmentPanel
        alignmentPending={false}
        alignmentError=""
        alignmentContext={{
          parents: [{ id: 1, title: "Parent Objective" }],
          children: [{ id: 2, title: "Child A" }, { id: 3, title: "Child B" }],
          all_objectives: [{ id: 5, title: "Objective 5" }],
          edges: [{ id: 77, parent_id: 1, child_id: 2, alignment_type: "SUPPORTS" }],
        }}
        alignmentDirection="parent"
        alignmentTargetObjectiveId=""
        onAlignmentDirectionChange={onDirectionChange}
        onAlignmentTargetObjectiveIdChange={onTargetChange}
        onAlignmentCreate={onCreate}
        onAlignmentDelete={onDelete}
      />,
    );

    expect(screen.getByText("Parents: 1 | Children: 2")).toBeInTheDocument();
    const selects = screen.getAllByRole("combobox");
    await user.selectOptions(selects[0], "child");
    await user.selectOptions(selects[1], "5");
    await user.click(screen.getByRole("button", { name: "Add link" }));
    await user.click(screen.getByRole("button", { name: "Remove" }));

    expect(onDirectionChange).toHaveBeenCalledWith("child");
    expect(onTargetChange).toHaveBeenCalledWith("5");
    expect(onCreate).toHaveBeenCalledTimes(1);
    expect(onDelete).toHaveBeenCalledWith(77);
  });
});
