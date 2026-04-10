import React from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import WeeklyModePanel from "@/components/atlas-shell/WeeklyModePanel";

describe("WeeklyModePanel", () => {
  it("wires export/ai/save actions and draft updates", async () => {
    const user = userEvent.setup();
    const onReportExport = vi.fn();
    const onGenerateAiSummary = vi.fn();
    const onSaveWeeklyPlan = vi.fn();
    const setWeeklyDraft = vi.fn();
    const draftTransitions: Array<{ p1: string; p2: string; p3: string }> = [];
    setWeeklyDraft.mockImplementation((arg) => {
      if (typeof arg === "function") {
        draftTransitions.push(arg({ p1: "", p2: "old", p3: "" }));
      }
    });

    render(
      <WeeklyModePanel
        weekRangeLabel="Jan 1 - Jan 7"
        cycleLabel="Q1 2026"
        reportExportPending={false}
        reportAiPending={false}
        reportExportError=""
        reportAiError=""
        onReportExport={onReportExport}
        onGenerateAiSummary={onGenerateAiSummary}
        weeklyTotalMinutes={320}
        weeklySessionCount={8}
        weeklyAverageMinutes={40}
        weeklyPriorityCoverage={{ pct: 67, filled: 2, total: 3 }}
        weeklyKrsNeedingCheckInCount={2}
        reportAiSummary={null}
        weeklyPlanData={{
          priority_1: "Close auth gap",
          priority_2: "Stabilize CI",
          priority_3: "Ship tests",
        }}
        weeklyDraft={{ p1: "", p2: "", p3: "" }}
        setWeeklyDraft={setWeeklyDraft}
        onSaveWeeklyPlan={onSaveWeeklyPlan}
        modeActionPending={false}
        weeklyTopTasks={[{ taskId: 7, title: "Auth hardening", minutes: 120, sessions: 3 }]}
        weeklyKrsNeedingCheckIn={[{ id: 12, title: "KR reliability", progress: 40 }]}
        weeklyReviewExperiments={[{ id: 91, status: "RUNNING", key_result_id: 12 }]}
      />,
    );

    expect(screen.getByText(/Jan 1 - Jan 7/i)).toBeInTheDocument();
    expect(screen.getByText(/320 min/i)).toBeInTheDocument();
    expect(screen.getByText(/8 sessions this week/i)).toBeInTheDocument();
    expect(screen.getByText(/67%/i)).toBeInTheDocument();
    expect(screen.getByText(/Auth hardening: 120 min \(3 sessions\)/i)).toBeInTheDocument();
    expect(screen.getByText(/KR reliability \(40%\)/i)).toBeInTheDocument();
    expect(screen.getByText(/#91/i)).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("Priority 1 (required)"), {
      target: { value: "Finalize auth migration" },
    });
    expect(draftTransitions[0]).toEqual({
      p1: "Finalize auth migration",
      p2: "old",
      p3: "",
    });

    await user.click(screen.getByRole("button", { name: "Export Weekly PDF" }));
    await user.click(screen.getByRole("button", { name: "Export Weekly HTML" }));
    await user.click(screen.getByRole("button", { name: "Generate AI Summary" }));
    await user.click(screen.getByRole("button", { name: "Save Weekly Priorities" }));

    expect(onReportExport).toHaveBeenNthCalledWith(1, "pdf");
    expect(onReportExport).toHaveBeenNthCalledWith(2, "html");
    expect(onGenerateAiSummary).toHaveBeenCalledTimes(1);
    expect(onSaveWeeklyPlan).toHaveBeenCalledTimes(1);
  });

  it("renders ai summary and error messages", () => {
    render(
      <WeeklyModePanel
        weekRangeLabel="Jan 1 - Jan 7"
        cycleLabel="Q1 2026"
        reportExportPending={false}
        reportAiPending={false}
        reportExportError="export failed"
        reportAiError="ai failed"
        onReportExport={vi.fn()}
        onGenerateAiSummary={vi.fn()}
        weeklyTotalMinutes={0}
        weeklySessionCount={0}
        weeklyAverageMinutes={0}
        weeklyPriorityCoverage={{ pct: 0, filled: 0, total: 3 }}
        weeklyKrsNeedingCheckInCount={0}
        reportAiSummary={{
          summaryMarkdown: "Weekly summary",
          highlights: ["Reduced drift", "Improved CI"],
          focusAnalysis: "Focus consistency improved",
        }}
        weeklyPlanData={null}
        weeklyDraft={{ p1: "", p2: "", p3: "" }}
        setWeeklyDraft={vi.fn()}
        onSaveWeeklyPlan={vi.fn()}
        modeActionPending={false}
        weeklyTopTasks={[]}
        weeklyKrsNeedingCheckIn={[]}
        weeklyReviewExperiments={[]}
      />,
    );

    expect(screen.getByText("export failed")).toBeInTheDocument();
    expect(screen.getByText("ai failed")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "AI Weekly Summary" })).toBeInTheDocument();
    expect(screen.getByText("Weekly summary")).toBeInTheDocument();
    expect(screen.getByText("Reduced drift")).toBeInTheDocument();
    expect(screen.getByText(/Focus analysis: Focus consistency improved/i)).toBeInTheDocument();
  });

  it("shows pending labels, disables controls, and renders empty-state fallbacks", () => {
    render(
      <WeeklyModePanel
        weekRangeLabel="Jan 1 - Jan 7"
        cycleLabel="Q1 2026"
        reportExportPending
        reportAiPending
        reportExportError=""
        reportAiError=""
        onReportExport={vi.fn()}
        onGenerateAiSummary={vi.fn()}
        weeklyTotalMinutes={0}
        weeklySessionCount={0}
        weeklyAverageMinutes={0}
        weeklyPriorityCoverage={{ pct: 0, filled: 0, total: 3 }}
        weeklyKrsNeedingCheckInCount={0}
        reportAiSummary={null}
        weeklyPlanData={null}
        weeklyDraft={{ p1: "", p2: "", p3: "" }}
        setWeeklyDraft={vi.fn()}
        onSaveWeeklyPlan={vi.fn()}
        modeActionPending
        weeklyTopTasks={[]}
        weeklyKrsNeedingCheckIn={[]}
        weeklyReviewExperiments={[]}
      />,
    );

    expect(screen.getByRole("button", { name: "Exporting..." })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Generating..." })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Saving..." })).toBeDisabled();
    expect(screen.getByText("No active weekly plan yet.")).toBeInTheDocument();
    expect(screen.getByText("No task-level focus logs this week.")).toBeInTheDocument();
    expect(screen.getByText("No outstanding KR check-ins this week.")).toBeInTheDocument();
    expect(screen.getByText("No experiments recorded in this review window.")).toBeInTheDocument();
  });
});
