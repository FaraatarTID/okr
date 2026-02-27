import React from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import AtlasModeControlsPanel from "@/components/atlas-shell/AtlasModeControlsPanel";

const sidebarItems = [
  { id: "atlas", label: "Atlas", mode: "atlas", path: "/atlas" },
  { id: "timeline", label: "Timeline", mode: "timeline", path: "/timeline" },
];

describe("AtlasModeControlsPanel", () => {
  it("renders controls and surfaced error messages", () => {
    render(
      <AtlasModeControlsPanel
        cycleLabel="Q3-2026"
        snapshotPending={false}
        cycleId="7"
        onCycleIdChange={vi.fn()}
        ownerIdsInput="1,2"
        onOwnerIdsInputChange={vi.fn()}
        mode="atlas"
        onModeChange={vi.fn()}
        sidebarItems={sidebarItems}
        lens="Scope"
        onLensChange={vi.fn()}
        parsedOwnerIdsError="owner parse error"
        cycleResolveError="cycle resolve error"
        snapshotError="snapshot error"
      />,
    );

    expect(screen.getByText("Cycle ID")).toBeInTheDocument();
    expect(screen.getByText("Owner IDs (optional)")).toBeInTheDocument();
    expect(screen.getByText("Mode")).toBeInTheDocument();
    expect(screen.getByText("Lens")).toBeInTheDocument();
    expect(screen.getByText("owner parse error")).toBeInTheDocument();
    expect(screen.getByText("cycle resolve error")).toBeInTheDocument();
    expect(screen.getByText("snapshot error")).toBeInTheDocument();
    expect(screen.getByText(/Auto-sync every 45s/)).toBeInTheDocument();
  });

  it("emits callbacks for cycle/owner/mode/lens changes and trims cycle id", async () => {
    const user = userEvent.setup();
    const onCycleIdChange = vi.fn();
    const onOwnerIdsInputChange = vi.fn();
    const onModeChange = vi.fn();
    const onLensChange = vi.fn();

    render(
      <AtlasModeControlsPanel
        cycleLabel="Q3-2026"
        snapshotPending
        cycleId=""
        onCycleIdChange={onCycleIdChange}
        ownerIdsInput=""
        onOwnerIdsInputChange={onOwnerIdsInputChange}
        mode="atlas"
        onModeChange={onModeChange}
        sidebarItems={sidebarItems}
        lens="Scope"
        onLensChange={onLensChange}
        parsedOwnerIdsError=""
        cycleResolveError=""
        snapshotError=""
      />,
    );

    fireEvent.change(screen.getByLabelText("Cycle ID"), { target: { value: " 42 " } });
    fireEvent.change(screen.getByLabelText("Owner IDs (optional)"), { target: { value: "1, 3" } });
    await user.selectOptions(screen.getByLabelText("Mode"), "timeline");
    await user.selectOptions(screen.getByLabelText("Lens"), "Branch");

    expect(onCycleIdChange).toHaveBeenCalledWith("42");
    expect(onOwnerIdsInputChange).toHaveBeenCalledWith("1, 3");
    expect(onModeChange).toHaveBeenCalledWith("timeline");
    expect(onLensChange).toHaveBeenCalledWith("Branch");
    expect(screen.getByText(/Loading/)).toBeInTheDocument();
  });
});
