import React from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import DailyModePanel from "@/components/atlas-shell/DailyModePanel";

describe("DailyModePanel", () => {
  it("renders daily stats and wires export/ai/filter callbacks", async () => {
    const user = userEvent.setup();
    const onReportExport = vi.fn();
    const onGenerateAiSummary = vi.fn();
    const onDailyLogQueryChange = vi.fn();

    render(
      <DailyModePanel
        todayLabel="2026-01-05"
        cycleLabel="Q1 2026"
        reportExportPending={false}
        reportAiPending={false}
        reportExportError=""
        reportAiError=""
        onReportExport={onReportExport}
        onGenerateAiSummary={onGenerateAiSummary}
        dailyLogsFiltered={[
          {
            id: 10,
            task_id: 7,
            duration_minutes: 55,
            start_time: "2026-01-05T09:00:00.000Z",
            summary: "Finalized session checks",
            task: { title: "Auth hardening" },
          },
        ]}
        dailyTotalMinutes={55}
        dailyAverageMinutes={55}
        dailyDeepWorkShare={100}
        reportAiSummary={null}
        dailyLogQuery=""
        onDailyLogQueryChange={onDailyLogQueryChange}
        dailyTimeBands={{ morning: 55, afternoon: 0, evening: 0 }}
        dailyTopTasks={[{ taskId: 7, title: "Auth hardening", minutes: 55, sessions: 1 }]}
        formatOptionalDate={(value) => String(value)}
      />,
    );

    expect(screen.getByText(/2026-01-05\s+.\s+Q1 2026/i)).toBeInTheDocument();
    expect(screen.getByText(/Auth hardening: 55 min \(1 sessions\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Minutes tracked today/i)).toBeInTheDocument();
    expect(screen.getByText(/Finalized session checks/i)).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("Filter by task, summary, or time"), {
      target: { value: "auth" },
    });
    expect(onDailyLogQueryChange).toHaveBeenCalledWith("auth");

    await user.click(screen.getByRole("button", { name: "Export Daily PDF" }));
    await user.click(screen.getByRole("button", { name: "Export Daily HTML" }));
    await user.click(screen.getByRole("button", { name: "Generate AI Summary" }));

    expect(onReportExport).toHaveBeenNthCalledWith(1, "pdf");
    expect(onReportExport).toHaveBeenNthCalledWith(2, "html");
    expect(onGenerateAiSummary).toHaveBeenCalledTimes(1);
  });

  it("renders ai summary with highlights and focus analysis", () => {
    render(
      <DailyModePanel
        todayLabel="2026-01-05"
        cycleLabel="Q1 2026"
        reportExportPending={false}
        reportAiPending={false}
        reportExportError=""
        reportAiError=""
        onReportExport={vi.fn()}
        onGenerateAiSummary={vi.fn()}
        dailyLogsFiltered={[]}
        dailyTotalMinutes={0}
        dailyAverageMinutes={0}
        dailyDeepWorkShare={0}
        reportAiSummary={{
          summaryMarkdown: "Daily summary",
          highlights: ["Resolved flaky gate"],
          focusAnalysis: "Strong morning block",
        }}
        dailyLogQuery=""
        onDailyLogQueryChange={vi.fn()}
        dailyTimeBands={{ morning: 0, afternoon: 0, evening: 0 }}
        dailyTopTasks={[]}
        formatOptionalDate={(value) => String(value)}
      />,
    );

    expect(screen.getByRole("heading", { name: "AI Daily Summary" })).toBeInTheDocument();
    expect(screen.getByText("Daily summary")).toBeInTheDocument();
    expect(screen.getByText("Resolved flaky gate")).toBeInTheDocument();
    expect(screen.getByText(/Focus analysis: Strong morning block/i)).toBeInTheDocument();
  });

  it("shows pending labels, errors, and empty-state fallbacks", () => {
    render(
      <DailyModePanel
        todayLabel="2026-01-05"
        cycleLabel="Q1 2026"
        reportExportPending
        reportAiPending
        reportExportError="export failed"
        reportAiError="ai failed"
        onReportExport={vi.fn()}
        onGenerateAiSummary={vi.fn()}
        dailyLogsFiltered={[]}
        dailyTotalMinutes={0}
        dailyAverageMinutes={0}
        dailyDeepWorkShare={0}
        reportAiSummary={null}
        dailyLogQuery=""
        onDailyLogQueryChange={vi.fn()}
        dailyTimeBands={{ morning: 0, afternoon: 0, evening: 0 }}
        dailyTopTasks={[]}
        formatOptionalDate={(value) => String(value)}
      />,
    );

    expect(screen.getByRole("button", { name: "Exporting..." })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Generating..." })).toBeDisabled();
    expect(screen.getByText("export failed")).toBeInTheDocument();
    expect(screen.getByText("ai failed")).toBeInTheDocument();
    expect(screen.getByText("No tasks captured in today logs.")).toBeInTheDocument();
    expect(screen.getByText("No logs for today (or no logs match the current filter).")).toBeInTheDocument();
  });
});
