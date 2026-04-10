import React from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import InspectorEditAnalysisPanel from "@/components/atlas-shell/InspectorEditAnalysisPanel";

describe("InspectorEditAnalysisPanel", () => {
  it("emits draft patch callbacks and mutation actions", async () => {
    const user = userEvent.setup();
    const onInspectDraftChange = vi.fn();
    const onInspectorSave = vi.fn();
    const onNodeDelete = vi.fn();
    const onRunAnalysis = vi.fn();

    render(
      <InspectorEditAnalysisPanel
        inspectDraft={{ title: "T", description: "D", progress: "10" }}
        onInspectDraftChange={onInspectDraftChange}
        onInspectorSave={onInspectorSave}
        inspectPending={false}
        hasUser
        rolloutAllowed
        onNodeDelete={onNodeDelete}
        deletePending={false}
        selectedTypeLabel="task"
        inspectError=""
        inspectMessage=""
        showAiAnalysis={false}
        aiAnalysisTargetLabel="key result"
        onRunAnalysis={onRunAnalysis}
        inspectAnalysisPending={false}
        inspectAnalysisError=""
        inspectAnalysis={null}
      />,
    );

    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "New title" } });
    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "New description" } });
    fireEvent.change(screen.getByLabelText("Progress (0-100)"), { target: { value: "45" } });

    expect(onInspectDraftChange).toHaveBeenCalledWith({ title: "New title" });
    expect(onInspectDraftChange).toHaveBeenCalledWith({ description: "New description" });
    expect(onInspectDraftChange).toHaveBeenCalledWith({ progress: "45" });

    await user.click(screen.getByRole("button", { name: "Edit" }));
    await user.click(screen.getByRole("button", { name: "Delete task" }));
    expect(onInspectorSave).toHaveBeenCalledTimes(1);
    expect(onNodeDelete).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("AI Analysis")).not.toBeInTheDocument();
  });

  it("disables mutation buttons when pending", () => {
    render(
      <InspectorEditAnalysisPanel
        inspectDraft={{ title: "T", description: "D", progress: "10" }}
        onInspectDraftChange={vi.fn()}
        onInspectorSave={vi.fn()}
        inspectPending
        hasUser
        rolloutAllowed
        onNodeDelete={vi.fn()}
        deletePending
        selectedTypeLabel="objective"
        inspectError="Update failed"
        inspectMessage="Saved"
        showAiAnalysis={false}
        aiAnalysisTargetLabel="objective"
        onRunAnalysis={vi.fn()}
        inspectAnalysisPending={false}
        inspectAnalysisError=""
        inspectAnalysis={null}
      />,
    );

    expect(screen.getByRole("button", { name: "Saving..." })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Deleting..." })).toBeDisabled();
    expect(screen.getByText("Update failed")).toBeInTheDocument();
    expect(screen.getByText("Saved")).toBeInTheDocument();
  });

  it("renders AI analysis section, triggers run action, and displays payload fields", async () => {
    const user = userEvent.setup();
    const onRunAnalysis = vi.fn();

    render(
      <InspectorEditAnalysisPanel
        inspectDraft={{ title: "T", description: "D", progress: "10" }}
        onInspectDraftChange={vi.fn()}
        onInspectorSave={vi.fn()}
        inspectPending={false}
        hasUser
        rolloutAllowed
        onNodeDelete={vi.fn()}
        deletePending={false}
        selectedTypeLabel="key result"
        inspectError=""
        inspectMessage=""
        showAiAnalysis
        aiAnalysisTargetLabel="objective"
        onRunAnalysis={onRunAnalysis}
        inspectAnalysisPending={false}
        inspectAnalysisError="analysis warning"
        inspectAnalysis={{
          efficiencyScore: 81,
          effectivenessScore: 79,
          overallScore: 80,
          summary: "Summary text",
          gapAnalysis: "Gap detail",
          qualityAssessment: "Quality detail",
          deadlineWarnings: ["Warn 1"],
          proposedTasks: ["Task A"],
        }}
      />,
    );

    expect(screen.getByText("AI Analysis")).toBeInTheDocument();
    expect(screen.getByText("Generate analysis for the selected objective.")).toBeInTheDocument();
    expect(screen.getByText("analysis warning")).toBeInTheDocument();
    expect(screen.getByText("Efficiency: 81")).toBeInTheDocument();
    expect(screen.getByText("Effectiveness: 79")).toBeInTheDocument();
    expect(screen.getByText("Overall: 80")).toBeInTheDocument();
    expect(screen.getByText("Summary text")).toBeInTheDocument();
    expect(screen.getByText("Gap: Gap detail")).toBeInTheDocument();
    expect(screen.getByText("Quality: Quality detail")).toBeInTheDocument();
    expect(screen.getByText("Warn 1")).toBeInTheDocument();
    expect(screen.getByText("Task A")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Run Analysis" }));
    expect(onRunAnalysis).toHaveBeenCalledTimes(1);
  });
});
