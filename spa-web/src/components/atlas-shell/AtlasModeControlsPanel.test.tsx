import React from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import AtlasModeControlsPanel from "@/components/atlas-shell/AtlasModeControlsPanel";

describe("AtlasModeControlsPanel", () => {
  it("renders controls and surfaced error messages", () => {
    render(
      <AtlasModeControlsPanel
        cycleLabel="Q3-2026"
        snapshotPending={false}
        snapshotPollIntervalMs={45000}
        cycleId="7"
        cycleOptions={[
          { id: 7, label: "Q3-2026" },
          { id: 8, label: "Q4-2026" },
        ]}
        canManageCycleSelection
        onCycleIdChange={vi.fn()}
        ownerIdsInput="1,2"
        onOwnerIdsInputChange={vi.fn()}
        canManageOwnerFilter
        ownerFilterOptions={[
          { id: 1, label: "Alice" },
          { id: 2, label: "Bob" },
        ]}
        selectedOwnerIds={[1, 2]}
        lens="focus"
        onLensChange={vi.fn()}
        parsedOwnerIdsError="owner parse error"
        cycleResolveError="cycle resolve error"
        snapshotError="snapshot error"
      />,
    );

    expect(screen.getByText("Cycle")).toBeInTheDocument();
    expect(screen.getByText("Owner Filter")).toBeInTheDocument();
    expect(screen.getByText("Leave empty to include all owners.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Alice x" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Bob x" })).toBeInTheDocument();
    expect(screen.getByText("Lens")).toBeInTheDocument();
    expect(screen.getByText("owner parse error")).toBeInTheDocument();
    expect(screen.getByText("cycle resolve error")).toBeInTheDocument();
    expect(screen.getByText("snapshot error")).toBeInTheDocument();
    expect(screen.getByText(/Auto-sync every 45s/)).toBeInTheDocument();
  });

  it("emits callbacks for cycle/owner/lens changes", async () => {
    const user = userEvent.setup();
    const onCycleIdChange = vi.fn();
    const onOwnerIdsInputChange = vi.fn();
    const onLensChange = vi.fn();

    render(
      <AtlasModeControlsPanel
        cycleLabel="Q3-2026"
        snapshotPending
        snapshotPollIntervalMs={45000}
        cycleId=""
        cycleOptions={[
          { id: 42, label: "Q4-2026" },
          { id: 7, label: "Q3-2026" },
        ]}
        canManageCycleSelection
        onCycleIdChange={onCycleIdChange}
        ownerIdsInput=""
        onOwnerIdsInputChange={onOwnerIdsInputChange}
        canManageOwnerFilter
        ownerFilterOptions={[
          { id: 1, label: "Alice" },
          { id: 3, label: "Charlie" },
        ]}
        selectedOwnerIds={[]}
        lens="focus"
        onLensChange={onLensChange}
        parsedOwnerIdsError=""
        cycleResolveError=""
        snapshotError=""
      />,
    );

    await user.selectOptions(screen.getByLabelText("Cycle"), "42");
    fireEvent.change(screen.getByLabelText("Owner Filter"), { target: { value: "Alice" } });
    await user.click(screen.getByRole("button", { name: "Add" }));
    fireEvent.change(screen.getByLabelText("Owner Filter"), { target: { value: "Charlie" } });
    await user.click(screen.getByRole("button", { name: "Add" }));
    await user.selectOptions(screen.getByLabelText("Lens"), "owner");

    expect(onCycleIdChange).toHaveBeenCalledWith("42");
    expect(onOwnerIdsInputChange).toHaveBeenCalledWith("1");
    expect(onOwnerIdsInputChange).toHaveBeenCalledWith("3");
    expect(onLensChange).toHaveBeenCalledWith("owner");
    expect(screen.getByText(/Loading/)).toBeInTheDocument();
  });

  it("hides owner filter controls for non-admin users", () => {
    render(
      <AtlasModeControlsPanel
        cycleLabel="Q3-2026"
        snapshotPending={false}
        snapshotPollIntervalMs={45000}
        cycleId="7"
        cycleOptions={[{ id: 7, label: "Q3-2026" }]}
        canManageCycleSelection={false}
        onCycleIdChange={vi.fn()}
        ownerIdsInput=""
        onOwnerIdsInputChange={vi.fn()}
        canManageOwnerFilter={false}
        ownerFilterOptions={[{ id: 1, label: "Alice" }]}
        selectedOwnerIds={[]}
        lens="focus"
        onLensChange={vi.fn()}
        parsedOwnerIdsError="owner parse error"
        cycleResolveError=""
        snapshotError=""
      />,
    );

    expect(screen.queryByText("Owner Filter")).not.toBeInTheDocument();
    expect(screen.queryByText("owner parse error")).not.toBeInTheDocument();
  });

  it("lets admins select an inactive visible manager cycle", async () => {
    const onCycleIdChange = vi.fn();
    const user = userEvent.setup();

    render(
      <AtlasModeControlsPanel
        cycleLabel="Q1-2026"
        snapshotPending={false}
        snapshotPollIntervalMs={45000}
        cycleId="8"
        cycleOptions={[
          { id: 7, label: "Cycle Manager#1", isActive: false },
          { id: 8, label: "Q3-2026", isActive: true },
        ]}
        canManageCycleSelection
        canInspectAllCycles
        onCycleIdChange={onCycleIdChange}
        ownerIdsInput=""
        onOwnerIdsInputChange={vi.fn()}
        canManageOwnerFilter
        ownerFilterOptions={[]}
        selectedOwnerIds={[]}
        lens="focus"
        onLensChange={vi.fn()}
        parsedOwnerIdsError=""
        cycleResolveError=""
        snapshotError=""
      />,
    );

    await user.selectOptions(screen.getByLabelText("Cycle"), "7");

    expect(onCycleIdChange).toHaveBeenCalledWith("7");
    expect(screen.getByRole("option", { name: "Cycle Manager#1" })).not.toBeDisabled();
  });
});
