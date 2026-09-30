import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import AtlasFocusMapPanel from "@/components/atlas-shell/AtlasFocusMapPanel";

type Node = { type: string; depth: number; title: string; progress: number; parent?: string | null; children?: string[]; ownerName?: string };

const index: Record<string, Node> = {
  goal_1: { type: "GOAL", depth: 0, title: "Build the most trusted planning platform", progress: 58, parent: null, children: ["objective_1"], ownerName: "Ari" },
  objective_1: { type: "OBJECTIVE", depth: 1, title: "Make planning feel effortless", progress: 72, parent: "goal_1", children: ["key_result_1"] },
  key_result_1: { type: "KEY_RESULT", depth: 2, title: "Cut time-to-first-plan in half", progress: 46, parent: "objective_1", children: ["task_1"] },
  task_1: { type: "TASK", depth: 3, title: "Ship the first-run experience", progress: 25, parent: "key_result_1", children: [] },
};

function renderMap(overrides: Partial<React.ComponentProps<typeof AtlasFocusMapPanel>> = {}) {
  return render(
    <AtlasFocusMapPanel
      filteredRefs={Object.keys(index)}
      atlasIndex={index}
      atlasRoots={["goal_1"]}
      selectedRef=""
      onSelectRef={vi.fn()}
      onOpenRef={vi.fn()}
      onAddChild={vi.fn()}
      onCreateGoal={vi.fn()}
      nodeQuery=""
      onNodeQueryChange={vi.fn()}
      hasSnapshotPayload
      nodeTagForType={(type) => ({ GOAL: "G", OBJECTIVE: "O", KEY_RESULT: "KR", TASK: "T" }[type] || "N")}
      {...overrides}
    />,
  );
}

describe("AtlasFocusMapPanel", () => {
  it("renders the Orbit Map and a labeled, connected hierarchy", () => {
    renderMap();

    expect(screen.getByRole("heading", { name: "Focus Map" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Strategy relationship map" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Select Goal: Build the most trusted planning platform/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Select Objective: Make planning feel effortless/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Select Key result: Cut time-to-first-plan in half/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Select Task: Ship the first-run experience/ })).toBeInTheDocument();
    expect(document.querySelector(".orbit-map__footer-stats")).toHaveTextContent("measures");
  });

  it("supports the synchronized outline view and selects a node", () => {
    const onSelectRef = vi.fn();
    renderMap({ onSelectRef });

    fireEvent.click(screen.getByRole("button", { name: /Outline/ }));
    const tree = screen.getByRole("tree", { name: "Strategy outline" });
    expect(within(tree).getByText("Build the most trusted planning platform")).toBeInTheDocument();
    fireEvent.click(within(tree).getByRole("button", { name: "Select Cut time-to-first-plan in half" }));
    expect(onSelectRef).toHaveBeenCalledWith("key_result_1");
  });

  it("selects on a single click and opens details only on double-click", () => {
    const onSelectRef = vi.fn();
    const onOpenRef = vi.fn();
    renderMap({ onSelectRef, onOpenRef });

    const label = screen.getByRole("button", { name: /Select Objective: Make planning feel effortless/ });
    fireEvent.click(label, { detail: 1 });
    expect(onSelectRef).toHaveBeenCalledWith("objective_1");
    expect(onOpenRef).not.toHaveBeenCalled();

    fireEvent.doubleClick(label);
    expect(onOpenRef).toHaveBeenCalledWith("objective_1");

    const core = screen.getByRole("button", { name: /^Key result: Cut time-to-first-plan in half/ });
    fireEvent.click(core, { detail: 1 });
    expect(onSelectRef).toHaveBeenLastCalledWith("key_result_1");
    fireEvent.doubleClick(core);
    expect(onOpenRef).toHaveBeenLastCalledWith("key_result_1");
  });

  it("opens details from the keyboard once a node is selected, and from the selection card", () => {
    const onSelectRef = vi.fn();
    const onOpenRef = vi.fn();
    renderMap({ selectedRef: "goal_1", onSelectRef, onOpenRef });

    const goal = screen.getByRole("button", { name: /^Goal: Build the most trusted planning platform/ });
    fireEvent.click(goal, { detail: 0 });
    expect(onOpenRef).toHaveBeenCalledWith("goal_1");
    expect(onSelectRef).not.toHaveBeenCalled();

    const other = screen.getByRole("button", { name: /^Objective: Make planning feel effortless/ });
    fireEvent.click(other, { detail: 0 });
    expect(onSelectRef).toHaveBeenCalledWith("objective_1");

    onOpenRef.mockClear();
    fireEvent.click(screen.getByRole("button", { name: "Open details" }));
    expect(onOpenRef).toHaveBeenCalledWith("goal_1");
  });

  it("uses the same single/double click behavior in the outline", () => {
    const onSelectRef = vi.fn();
    const onOpenRef = vi.fn();
    renderMap({ onSelectRef, onOpenRef });
    fireEvent.click(screen.getByRole("button", { name: /Outline/ }));
    const row = within(screen.getByRole("tree", { name: "Strategy outline" })).getByRole("button", { name: "Select Make planning feel effortless" });
    fireEvent.click(row, { detail: 1 });
    expect(onOpenRef).not.toHaveBeenCalled();
    fireEvent.doubleClick(row);
    expect(onOpenRef).toHaveBeenCalledWith("objective_1");
  });

  it("focuses the selected path and exposes contextual add actions", () => {
    const onSelectRef = vi.fn();
    const onAddChild = vi.fn();
    renderMap({ selectedRef: "key_result_1", onSelectRef, onAddChild });

    expect(screen.getByRole("navigation", { name: "Selected outcome path" })).toHaveTextContent(
      /Build the most trusted planning platform.*Make planning feel effortless.*Cut time-to-first-plan in half/,
    );
    fireEvent.click(screen.getByRole("button", { name: /Focus path/ }));
    expect(screen.getByRole("button", { name: /Select Task: Ship the first-run experience/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Add task/ }));
    expect(onAddChild).toHaveBeenCalledWith("key_result_1");
  });

  it("collapses and expands a branch in outline view", () => {
    renderMap();
    fireEvent.click(screen.getByRole("button", { name: /Outline/ }));
    const tree = screen.getByRole("tree", { name: "Strategy outline" });
    expect(within(tree).getByText("Ship the first-run experience")).toBeInTheDocument();
    fireEvent.click(within(tree).getByRole("button", { name: "Collapse Build the most trusted planning platform" }));
    expect(within(tree).queryByText("Ship the first-run experience")).not.toBeInTheDocument();
    fireEvent.click(within(tree).getByRole("button", { name: "Expand Build the most trusted planning platform" }));
    expect(within(tree).getByText("Ship the first-run experience")).toBeInTheDocument();
  });

  it("keeps matching descendants when search filters out their ancestors", () => {
    renderMap({ filteredRefs: ["task_1"], nodeQuery: "first-run" });
    expect(screen.getByRole("button", { name: /Select Task: Ship the first-run experience/ })).toBeInTheDocument();
    expect(screen.getByText(/1 match/)).toBeInTheDocument();
  });

  it("offers a useful empty state when there are no goals yet", () => {
    renderMap({ filteredRefs: [], atlasIndex: {}, atlasRoots: [], hasSnapshotPayload: true });
    expect(screen.getByText("No matching outcomes. Try another search.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create your first goal" })).toBeInTheDocument();
  });
});
