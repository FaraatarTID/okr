"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { startTaskTimer, stopTaskTimer, type AuthUser } from "@/lib/api";
import {
  formatElapsedClock,
  formatOptionalDate,
  parseDateOrNull,
} from "@/components/atlas-shell/shellDateUtils";

type UseTimerSessionInput = {
  user: AuthUser | null;
  rolloutAllowed: boolean;
  focusTaskId: number | null;
  focusTaskStartedAt: string;
  parsedCycleId: number | null;
  mode: string;
  loadSnapshotForUser: (activeUser: AuthUser) => Promise<void>;
  refreshDashboardModeData: (activeUser: AuthUser, activeMode: string) => Promise<void>;
};

export default function useTimerSession({
  user,
  rolloutAllowed,
  focusTaskId,
  focusTaskStartedAt,
  parsedCycleId,
  mode,
  loadSnapshotForUser,
  refreshDashboardModeData,
}: UseTimerSessionInput) {
  const [timerPending, setTimerPending] = useState(false);
  const [timerSummary, setTimerSummary] = useState("");
  const [timerError, setTimerError] = useState("");
  const [timerMessage, setTimerMessage] = useState("");
  const [timerModalOpen, setTimerModalOpen] = useState(false);
  const [timerSessionStartAt, setTimerSessionStartAt] = useState("");
  const [timerSessionTaskId, setTimerSessionTaskId] = useState<number | null>(null);
  const [timerClockNowMs, setTimerClockNowMs] = useState(() => Date.now());

  const focusTaskRunning = useMemo(() => {
    if (String(timerSessionStartAt || "").trim()) {
      return true;
    }
    return Boolean(String(focusTaskStartedAt || "").trim());
  }, [focusTaskStartedAt, timerSessionStartAt]);

  const activeTimerStartedAt = useMemo(() => {
    const explicit = String(timerSessionStartAt || "").trim();
    if (explicit) {
      return explicit;
    }
    return String(focusTaskStartedAt || "").trim();
  }, [focusTaskStartedAt, timerSessionStartAt]);

  const activeTimerElapsedSeconds = useMemo(() => {
    const parsed = parseDateOrNull(activeTimerStartedAt);
    if (!parsed) {
      return 0;
    }
    return Math.max(0, Math.floor((timerClockNowMs - parsed.getTime()) / 1000));
  }, [activeTimerStartedAt, timerClockNowMs]);

  useEffect(() => {
    if (!focusTaskId || !focusTaskRunning) {
      return;
    }
    if (!timerSessionTaskId) {
      setTimerSessionTaskId(focusTaskId);
    }
  }, [focusTaskId, focusTaskRunning, timerSessionTaskId]);

  useEffect(() => {
    if (!timerModalOpen || !focusTaskRunning) {
      return;
    }
    setTimerClockNowMs(Date.now());
    const timerId = window.setInterval(() => {
      setTimerClockNowMs(Date.now());
    }, 1000);
    return () => {
      window.clearInterval(timerId);
    };
  }, [timerModalOpen, focusTaskRunning, activeTimerStartedAt]);

  useEffect(() => {
    if (focusTaskRunning) {
      return;
    }
    setTimerModalOpen(false);
    setTimerSessionStartAt("");
    setTimerSessionTaskId(null);
  }, [focusTaskRunning]);

  const handleTimerStart = useCallback(async (): Promise<void> => {
    if (!user || !focusTaskId || !rolloutAllowed) {
      return;
    }
    setTimerPending(true);
    setTimerError("");
    setTimerMessage("");
    try {
      const response = await startTaskTimer({
        actor_username: user.username,
        task_id: focusTaskId,
      });
      const parsedStart = parseDateOrNull(response.start_time);
      const resumedElapsedSeconds = parsedStart
        ? Math.max(0, Math.floor((Date.now() - parsedStart.getTime()) / 1000))
        : 0;
      if (resumedElapsedSeconds >= 60) {
        setTimerMessage(
          `Timer resumed for task #${response.task_id} (already running for ${formatElapsedClock(resumedElapsedSeconds)}).`,
        );
      } else {
        setTimerMessage(
          `Timer started for task #${response.task_id} at ${formatOptionalDate(response.start_time)}.`,
        );
      }
      setTimerSessionTaskId(response.task_id);
      setTimerSessionStartAt(String(response.start_time || ""));
      setTimerClockNowMs(Date.now());
      setTimerModalOpen(true);
      if (parsedCycleId) {
        await loadSnapshotForUser(user);
      }
      if (mode === "dashboard" || mode === "timeline") {
        await refreshDashboardModeData(user, mode);
      }
    } catch (error) {
      setTimerError(String(error instanceof Error ? error.message : error));
    } finally {
      setTimerPending(false);
    }
  }, [
    focusTaskId,
    loadSnapshotForUser,
    mode,
    parsedCycleId,
    refreshDashboardModeData,
    rolloutAllowed,
    user,
  ]);

  const handleTimerStop = useCallback(async (): Promise<void> => {
    if (!user || !rolloutAllowed) {
      return;
    }
    const resolvedTaskId = timerSessionTaskId || focusTaskId || null;
    if (!resolvedTaskId) {
      setTimerError("No running task timer was found.");
      return;
    }
    setTimerPending(true);
    setTimerError("");
    setTimerMessage("");
    try {
      const response = await stopTaskTimer({
        actor_username: user.username,
        task_id: resolvedTaskId,
        summary: timerSummary,
      });
      setTimerMessage(
        `Timer stopped for task #${response.task_id}; duration ${response.duration_minutes} min.`,
      );
      setTimerSessionTaskId(null);
      setTimerSessionStartAt("");
      setTimerModalOpen(false);
      setTimerSummary("");
      if (parsedCycleId) {
        await loadSnapshotForUser(user);
      }
      if (mode === "dashboard" || mode === "timeline") {
        await refreshDashboardModeData(user, mode);
      }
    } catch (error) {
      setTimerError(String(error instanceof Error ? error.message : error));
    } finally {
      setTimerPending(false);
    }
  }, [
    focusTaskId,
    loadSnapshotForUser,
    mode,
    parsedCycleId,
    refreshDashboardModeData,
    rolloutAllowed,
    timerSessionTaskId,
    timerSummary,
    user,
  ]);

  return {
    timerPending,
    timerSummary,
    setTimerSummary,
    timerError,
    timerMessage,
    timerModalOpen,
    setTimerModalOpen,
    focusTaskRunning,
    activeTimerStartedAt,
    activeTimerElapsedSeconds,
    handleTimerStart,
    handleTimerStop,
  };
}
