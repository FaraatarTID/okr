import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import * as React from "react";

import useModeStateReset from "@/components/atlas-shell/useModeStateReset";

type HarnessProps = {
  mode: string;
  timelineQuery: string;
  timelineStatusFilter: "all" | "todo" | "in_progress" | "done" | "blocked" | "overdue";
  dailyLogQuery: string;
  ritualStep: 1 | 2 | 3;
};

function renderResetHook(initialProps: HarnessProps) {
  return renderHook((props: HarnessProps) => {
    const [timelineQuery, setTimelineQuery] = React.useState(props.timelineQuery);
    const [timelineStatusFilter, setTimelineStatusFilter] = React.useState(props.timelineStatusFilter);
    const [dailyLogQuery, setDailyLogQuery] = React.useState(props.dailyLogQuery);
    const [ritualStep, setRitualStep] = React.useState(props.ritualStep);

    useModeStateReset({
      mode: props.mode,
      setTimelineQuery,
      setTimelineStatusFilter,
      setDailyLogQuery,
      setRitualStep,
    });

    return {
      timelineQuery,
      timelineStatusFilter,
      dailyLogQuery,
      ritualStep,
    };
  }, { initialProps });
}

describe("useModeStateReset", () => {
  it("clears timeline filters outside timeline mode", async () => {
    const { result } = renderResetHook({
      mode: "atlas",
      timelineQuery: "critical",
      timelineStatusFilter: "blocked",
      dailyLogQuery: "",
      ritualStep: 2,
    });

    await waitFor(() => {
      expect(result.current.timelineQuery).toBe("");
      expect(result.current.timelineStatusFilter).toBe("all");
    });
  });

  it("preserves timeline filters in timeline mode", async () => {
    const { result } = renderResetHook({
      mode: "timeline",
      timelineQuery: "critical",
      timelineStatusFilter: "blocked",
      dailyLogQuery: "",
      ritualStep: 2,
    });

    await waitFor(() => {
      expect(result.current.timelineQuery).toBe("critical");
      expect(result.current.timelineStatusFilter).toBe("blocked");
    });
  });

  it("clears daily query outside daily mode", async () => {
    const { result } = renderResetHook({
      mode: "weekly",
      timelineQuery: "",
      timelineStatusFilter: "all",
      dailyLogQuery: "review",
      ritualStep: 2,
    });

    await waitFor(() => {
      expect(result.current.dailyLogQuery).toBe("");
    });
  });

  it("resets ritual step to first step when entering ritual mode", async () => {
    const { result } = renderResetHook({
      mode: "ritual",
      timelineQuery: "",
      timelineStatusFilter: "all",
      dailyLogQuery: "",
      ritualStep: 3,
    });

    await waitFor(() => {
      expect(result.current.ritualStep).toBe(1);
    });
  });
});
