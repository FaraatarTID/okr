import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import InspectorAiAssistPanel from "@/components/atlas-shell/InspectorAiAssistPanel";

describe("InspectorAiAssistPanel", () => {
  it("triggers analysis action", async () => {
    const user = userEvent.setup();
    const onRunAiSync = vi.fn();

    render(
      <InspectorAiAssistPanel
        aiSyncPending={false}
        hasUser
        hasAtlasRuntime
        aiSyncReport={null}
        aiSyncError=""
        aiSyncMessage=""
        onRunAiSync={onRunAiSync}
      />,
    );

    await user.click(screen.getByRole("button", { name: "AI Analysis" }));
    expect(onRunAiSync).toHaveBeenCalledTimes(1);
  });

  it("disables button when pending", () => {
    render(
      <InspectorAiAssistPanel
        aiSyncPending
        hasUser
        hasAtlasRuntime
        aiSyncReport={null}
        aiSyncError=""
        aiSyncMessage=""
        onRunAiSync={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Analyzing..." })).toBeDisabled();
  });

  it("renders report with reanalyzed count and errors", () => {
    render(
      <InspectorAiAssistPanel
        aiSyncPending={false}
        hasUser
        hasAtlasRuntime
        aiSyncReport={{
          total: 4,
          analyzed: 4,
          reanalyzed: 2,
          unchanged: 2,
          failed: ["KR-9: analysis failed"],
        }}
        aiSyncError="sync error"
        aiSyncMessage="sync message"
        onRunAiSync={vi.fn()}
      />,
    );

    expect(screen.getByText(/Analyzed 2 KRs \(2 cached\)/)).toBeInTheDocument();
    expect(screen.getByText("sync error")).toBeInTheDocument();
    expect(screen.getByText("sync message")).toBeInTheDocument();
    expect(screen.getByText("KR-9: analysis failed")).toBeInTheDocument();
  });
});
