import React from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import TimelineModePanel from "@/components/atlas-shell/TimelineModePanel";

const DEFAULT_WINDOW = {
  start: new Date("2026-01-01T00:00:00.000Z"),
  end: new Date("2026-01-11T00:00:00.000Z"),
  spanMs: 10 * 24 * 60 * 60 * 1000,
  todayLeftPct: 40,
};

const DEFAULT_ROWS = [
  {
    id: 7,
    title: "Close auth boundary gap",
    status: "IN_PROGRESS",
    progress: 55,
    assigneeName: "Alex",
    keyResultTitle: "KR-7",
    objectiveTitle: "Ship secure session model",
    goalTitle: "Stabilize SPA",
    startAt: new Date("2026-01-02T00:00:00.000Z"),
    endAt: new Date("2026-01-06T00:00:00.000Z"),
    isProjectedEnd: false,
    isOverdue: false,
  },
];

const DEFAULT_STATUS_COUNTS = {
  todo: 0,
  inProgress: 1,
  done: 0,
  blocked: 0,
  overdue: 0,
};

describe("TimelineModePanel", () => {
  it("renders gantt content and wires filter/action callbacks", async () => {
    const user = userEvent.setup();
    const onTimelineQueryChange = vi.fn();
    const onTimelineStatusFilterChange = vi.fn();
    const onOpenTaskInAtlas = vi.fn();

    render(
      <TimelineModePanel
        timelineRows={DEFAULT_ROWS}
        timelineRowsFiltered={DEFAULT_ROWS}
        timelineStatusCounts={DEFAULT_STATUS_COUNTS}
        timelineQuery=""
        onTimelineQueryChange={onTimelineQueryChange}
        timelineStatusFilter="all"
        onTimelineStatusFilterChange={onTimelineStatusFilterChange}
        timelineWindow={DEFAULT_WINDOW}
        timelineLogs={[
          {
            id: 1001,
            task_id: 7,
            duration_minutes: 37,
            start_time: "2026-01-03T14:00:00.000Z",
            task: { title: "Close auth boundary gap" },
          },
        ]}
        timelineStatusLabel={(value) => value.toLowerCase().replace("_", " ")}
        toDateShortLabel={(value) => value.toISOString().slice(0, 10)}
        formatOptionalDate={(value) => String(value)}
        onOpenTaskInAtlas={onOpenTaskInAtlas}
      />,
    );

    expect(screen.getByText("Tasks in cycle: 1")).toBeInTheDocument();
    expect(screen.getByText("Visible: 1")).toBeInTheDocument();
    expect(screen.getByText("Project Gantt")).toBeInTheDocument();
    expect(screen.getAllByText("Close auth boundary gap")).toHaveLength(2);
    expect(screen.getByText(/2026-01-03T14:00:00.000Z/i)).toBeInTheDocument();
    expect(screen.getByText(/37 min/i)).toBeInTheDocument();

    const queryInput = screen.getByPlaceholderText(
      "Filter timeline by task, owner, objective, goal, or status",
    );
    fireEvent.change(queryInput, { target: { value: "risk" } });
    expect(onTimelineQueryChange).toHaveBeenCalledWith("risk");

    await user.selectOptions(screen.getByRole("combobox"), "done");
    expect(onTimelineStatusFilterChange).toHaveBeenCalledWith("done");

    await user.click(screen.getByRole("button", { name: "Open in Atlas" }));
    expect(onOpenTaskInAtlas).toHaveBeenCalledWith(7);
  });

  it("renders empty-state fallback when no timeline window is available", () => {
    const { rerender } = render(
      <TimelineModePanel
        timelineRows={[]}
        timelineRowsFiltered={[]}
        timelineStatusCounts={{ todo: 0, inProgress: 0, done: 0, blocked: 0, overdue: 0 }}
        timelineQuery=""
        onTimelineQueryChange={vi.fn()}
        timelineStatusFilter="all"
        onTimelineStatusFilterChange={vi.fn()}
        timelineWindow={null}
        timelineLogs={[]}
        timelineStatusLabel={(value) => value}
        toDateShortLabel={(value) => value.toISOString()}
        formatOptionalDate={(value) => String(value)}
        onOpenTaskInAtlas={vi.fn()}
      />,
    );

    expect(screen.getByText("No tasks found for the current cycle.")).toBeInTheDocument();
    expect(screen.getByText("No recent work logs for current actor.")).toBeInTheDocument();

    rerender(
      <TimelineModePanel
        timelineRows={[]}
        timelineRowsFiltered={[]}
        timelineStatusCounts={{ todo: 0, inProgress: 0, done: 0, blocked: 0, overdue: 0 }}
        timelineQuery="atlas"
        onTimelineQueryChange={vi.fn()}
        timelineStatusFilter="all"
        onTimelineStatusFilterChange={vi.fn()}
        timelineWindow={null}
        timelineLogs={[]}
        timelineStatusLabel={(value) => value}
        toDateShortLabel={(value) => value.toISOString()}
        formatOptionalDate={(value) => String(value)}
        onOpenTaskInAtlas={vi.fn()}
      />,
    );

    expect(screen.getByText("No tasks match current timeline filters.")).toBeInTheDocument();
  });

  it("shows filtered-empty message inside gantt when no rows match", () => {
    render(
      <TimelineModePanel
        timelineRows={DEFAULT_ROWS}
        timelineRowsFiltered={[]}
        timelineStatusCounts={DEFAULT_STATUS_COUNTS}
        timelineQuery=""
        onTimelineQueryChange={vi.fn()}
        timelineStatusFilter="all"
        onTimelineStatusFilterChange={vi.fn()}
        timelineWindow={DEFAULT_WINDOW}
        timelineLogs={[]}
        timelineStatusLabel={(value) => value}
        toDateShortLabel={(value) => value.toISOString()}
        formatOptionalDate={(value) => String(value)}
        onOpenTaskInAtlas={vi.fn()}
      />,
    );

    expect(screen.getByText("No tasks match current timeline filters.")).toBeInTheDocument();
  });
});
