import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import InspectorAiAssistPanel from "@/components/atlas-shell/InspectorAiAssistPanel";

describe("InspectorAiAssistPanel", () => {
  it("triggers all enabled actions", async () => {
    const user = userEvent.setup();
    const onPreviewAiSync = vi.fn();
    const onApplyAiSync = vi.fn();
    const onUndoAiSync = vi.fn();
    const onSuggestNextTask = vi.fn();

    render(
      <InspectorAiAssistPanel
        aiSyncMaxDelta={10}
        aiSyncPending={false}
        aiSuggestPending={false}
        hasUser
        hasAtlasRuntime

        hasAiUndoItems
        hasTaskRefs
        aiSyncReport={null}
        aiSuggestion={null}
        aiSyncError=""
        aiSyncMessage=""
        onPreviewAiSync={onPreviewAiSync}
        onApplyAiSync={onApplyAiSync}
        onUndoAiSync={onUndoAiSync}
        onSuggestNextTask={onSuggestNextTask}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Preview AI Sync" }));
    await user.click(screen.getByRole("button", { name: "Apply AI Sync" }));
    await user.click(screen.getByRole("button", { name: "Undo Sync" }));
    await user.click(screen.getByRole("button", { name: "Suggest Next Task" }));

    expect(onPreviewAiSync).toHaveBeenCalledTimes(1);
    expect(onApplyAiSync).toHaveBeenCalledTimes(1);
    expect(onUndoAiSync).toHaveBeenCalledTimes(1);
    expect(onSuggestNextTask).toHaveBeenCalledTimes(1);
  });

  it("disables actions when runtime/permissions/pending constraints apply", () => {
    render(
      <InspectorAiAssistPanel
        aiSyncMaxDelta={10}
        aiSyncPending
        aiSuggestPending={false}
        hasUser
        hasAtlasRuntime

        hasAiUndoItems
        hasTaskRefs
        aiSyncReport={null}
        aiSuggestion={null}
        aiSyncError=""
        aiSyncMessage=""
        onPreviewAiSync={vi.fn()}
        onApplyAiSync={vi.fn()}
        onUndoAiSync={vi.fn()}
        onSuggestNextTask={vi.fn()}
      />,
    );

    expect(screen.getAllByRole("button", { name: "Working..." })).toHaveLength(3);
    expect(screen.getByRole("button", { name: "Suggest Next Task" })).toBeDisabled();
  });

  it("renders report, suggestion, errors/messages, and failed rows", () => {
    render(
      <InspectorAiAssistPanel
        aiSyncMaxDelta={12}
        aiSyncPending={false}
        aiSuggestPending={false}
        hasUser
        hasAtlasRuntime

        hasAiUndoItems={false}
        hasTaskRefs={false}
        aiSyncReport={{
          total: 4,
          analyzed: 4,
          applied: 3,
          planned: 3,
          missingAiScore: 1,
          skippedDeltaCap: 0,
          skippedDecrease: 1,
          unchanged: 0,
          failed: ["KR-9: update rejected"],
        }}
        aiSuggestion={{
          taskRef: "task_42",
          reason: "highest risk-adjusted impact",
          confidence: 88,
        }}
        aiSyncError="sync error"
        aiSyncMessage="sync message"
        onPreviewAiSync={vi.fn()}
        onApplyAiSync={vi.fn()}
        onUndoAiSync={vi.fn()}
        onSuggestNextTask={vi.fn()}
      />,
    );

    expect(screen.getByText(/Analyzed 4 of 4 KRs/)).toBeInTheDocument();
    expect(screen.getByText(/3 updates? applied/)).toBeInTheDocument();
    expect(
      screen.getByText("Suggested: task_42 (88% confidence) - highest risk-adjusted impact"),
    ).toBeInTheDocument();
    expect(screen.getByText("sync error")).toBeInTheDocument();
    expect(screen.getByText("sync message")).toBeInTheDocument();
    expect(screen.getByText("KR-9: update rejected")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Undo Sync" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Suggest Next Task" })).toBeDisabled();
  });
});
