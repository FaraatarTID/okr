"use client";

import { useEffect, type Dispatch, type SetStateAction } from "react";

type TimelineStatus = "all" | "todo" | "in_progress" | "done" | "blocked" | "overdue";

type UseModeStateResetInput = {
  mode: string;
  setTimelineQuery: Dispatch<SetStateAction<string>>;
  setTimelineStatusFilter: Dispatch<SetStateAction<TimelineStatus>>;
  setDailyLogQuery: Dispatch<SetStateAction<string>>;
  setRitualStep: Dispatch<SetStateAction<1 | 2 | 3>>;
};

export default function useModeStateReset({
  mode,
  setTimelineQuery,
  setTimelineStatusFilter,
  setDailyLogQuery,
  setRitualStep,
}: UseModeStateResetInput) {
  useEffect(() => {
    if (mode !== "timeline") {
      setTimelineQuery("");
      setTimelineStatusFilter("all");
    }
  }, [mode, setTimelineQuery, setTimelineStatusFilter]);

  useEffect(() => {
    if (mode !== "daily") {
      setDailyLogQuery("");
    }
  }, [mode, setDailyLogQuery]);

  useEffect(() => {
    if (mode !== "ritual") {
      return;
    }
    setRitualStep(1);
  }, [mode, setRitualStep]);
}
