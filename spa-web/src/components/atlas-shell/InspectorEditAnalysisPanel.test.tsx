import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import InspectorEditAnalysisPanel from "@/components/atlas-shell/InspectorEditAnalysisPanel";

describe("InspectorEditAnalysisPanel", () => {
  it("renders edit form and triggers save/delete actions", async () => {
    const user = userEvent.setup();
    const onInspectorSave = vi.fn();
    const onNodeDelete = vi.fn();

    render(
      <InspectorEditAnalysisPanel
        inspectDraft={{ title: "T", description: "D", progress: "10", startValue: "", targetValue: "", deadline: "", estimatedMinutes: "30" }}
        onInspectDraftChange={vi.fn()}
        onInspectorSave={onInspectorSave}
        inspectPending={false}
        hasUser

        onNodeDelete={onNodeDelete}
        deletePending={false}
        deleteError=""
        deleteMessage=""
        selectedTypeLabel="task"
        selectedNodeType="TASK"
        inspectError=""
        inspectMessage=""
        inspectAnalysis={null}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Edit" }));
    await user.click(screen.getByRole("button", { name: "Delete task" }));
    expect(onInspectorSave).toHaveBeenCalledTimes(1);
    expect(onNodeDelete).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("AI Analysis")).not.toBeInTheDocument();
  });

  it("disables mutation buttons when pending", () => {
    render(
      <InspectorEditAnalysisPanel
        inspectDraft={{ title: "T", description: "D", progress: "10", startValue: "", targetValue: "", deadline: "", estimatedMinutes: "30" }}
        onInspectDraftChange={vi.fn()}
        onInspectorSave={vi.fn()}
        inspectPending
        hasUser

        onNodeDelete={vi.fn()}
        deletePending
        deleteError=""
        deleteMessage=""
        selectedTypeLabel="objective"
        selectedNodeType="OBJECTIVE"
        inspectError="Update failed"
        inspectMessage="Saved"
        inspectAnalysis={null}
      />,
    );

    expect(screen.getByRole("button", { name: "Saving..." })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Deleting..." })).toBeDisabled();
    expect(screen.getByText("Update failed")).toBeInTheDocument();
    expect(screen.getByText("Saved")).toBeInTheDocument();
  });

  it("shows read-only analysis when analysis data exists", () => {
    render(
      <InspectorEditAnalysisPanel
        inspectDraft={{ title: "T", description: "D", progress: "10", startValue: "", targetValue: "", deadline: "", estimatedMinutes: "30" }}
        onInspectDraftChange={vi.fn()}
        onInspectorSave={vi.fn()}
        inspectPending={false}
        hasUser

        onNodeDelete={vi.fn()}
        deletePending={false}
        deleteError=""
        deleteMessage=""
        selectedTypeLabel="key result"
        selectedNodeType="KEY_RESULT"
        inspectError=""
        inspectMessage=""
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
    expect(screen.getByText("Efficiency: 81")).toBeInTheDocument();
    expect(screen.getByText("Effectiveness: 79")).toBeInTheDocument();
    expect(screen.getByText("Overall: 80")).toBeInTheDocument();
    expect(screen.getByText("Summary text")).toBeInTheDocument();
    expect(screen.getByText("Gap: Gap detail")).toBeInTheDocument();
    expect(screen.getByText("Quality: Quality detail")).toBeInTheDocument();
    expect(screen.getByText("Warn 1")).toBeInTheDocument();
    expect(screen.getByText("Task A")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Run Analysis" })).not.toBeInTheDocument();
  });

  it("shows Run Analysis button for KR when no analysis data exists", async () => {
    const user = userEvent.setup();
    const onRunAnalysis = vi.fn();

    render(
      <InspectorEditAnalysisPanel
        inspectDraft={{ title: "T", description: "D", progress: "10", startValue: "", targetValue: "", deadline: "", estimatedMinutes: "30" }}
        onInspectDraftChange={vi.fn()}
        onInspectorSave={vi.fn()}
        inspectPending={false}
        hasUser

        onNodeDelete={vi.fn()}
        deletePending={false}
        deleteError=""
        deleteMessage=""
        selectedTypeLabel="key result"
        selectedNodeType="KEY_RESULT"
        inspectError=""
        inspectMessage=""
        inspectAnalysis={null}
        onRunAnalysis={onRunAnalysis}
      />,
    );

    expect(screen.getByText("AI Analysis")).toBeInTheDocument();
    expect(screen.getByText("No analysis yet for this Key Result.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Run Analysis" }));
    expect(onRunAnalysis).toHaveBeenCalledTimes(1);
  });

  it("shows no AI analysis section for Objective", () => {
    render(
      <InspectorEditAnalysisPanel
        inspectDraft={{ title: "T", description: "D", progress: "10", startValue: "", targetValue: "", deadline: "", estimatedMinutes: "30" }}
        onInspectDraftChange={vi.fn()}
        onInspectorSave={vi.fn()}
        inspectPending={false}
        hasUser

        onNodeDelete={vi.fn()}
        deletePending={false}
        deleteError=""
        deleteMessage=""
        selectedTypeLabel="objective"
        selectedNodeType="OBJECTIVE"
        inspectError=""
        inspectMessage=""
        inspectAnalysis={null}
      />,
    );

    expect(screen.queryByText("AI Analysis")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Run Analysis" })).not.toBeInTheDocument();
  });
});
