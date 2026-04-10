"use client";

import { useCallback, useState, type Dispatch, type SetStateAction } from "react";

import {
  createRetrospectiveMutation,
  createWeeklyPlanMutation,
  type AuthUser,
} from "@/lib/api";

type WeeklyDraft = {
  p1: string;
  p2: string;
  p3: string;
};

type RetroDraft = {
  content: string;
  sentiment: string;
};

type UseModeActionsInput = {
  user: AuthUser | null;
  parsedCycleId: number | null;
  weeklyDraft: WeeklyDraft;
  retroDraft: RetroDraft;
  setRetroDraft: Dispatch<SetStateAction<RetroDraft>>;
  loadModeData: (activeUser: AuthUser, nextMode: string) => Promise<void>;
  startOfWeekIso: () => string;
  endOfWeekIso: () => string;
  toIsoStart: (dateValue: string) => string;
  toIsoEnd: (dateValue: string) => string;
};

export default function useModeActions({
  user,
  parsedCycleId,
  weeklyDraft,
  retroDraft,
  setRetroDraft,
  loadModeData,
  startOfWeekIso,
  endOfWeekIso,
  toIsoStart,
  toIsoEnd,
}: UseModeActionsInput) {
  const [modeActionPending, setModeActionPending] = useState(false);
  const [modeActionMessage, setModeActionMessage] = useState("");
  const [modeActionError, setModeActionError] = useState("");

  const handleWeeklyPlanSave = useCallback(
    async (refreshMode: "weekly" | "ritual" = "weekly"): Promise<void> => {
      if (!user) {
        return;
      }
      const priority1 = weeklyDraft.p1.trim();
      if (!priority1) {
        setModeActionError("Priority 1 is required.");
        setModeActionMessage("");
        return;
      }
      setModeActionPending(true);
      setModeActionError("");
      setModeActionMessage("");
      try {
        const start = startOfWeekIso();
        const end = endOfWeekIso();
        await createWeeklyPlanMutation({
          actor_username: user.username,
          user_id: user.id,
          start_date: toIsoStart(start),
          end_date: toIsoEnd(end),
          p1: priority1,
          p2: weeklyDraft.p2.trim(),
          p3: weeklyDraft.p3.trim(),
        });
        setModeActionMessage("Weekly priorities saved.");
        await loadModeData(user, refreshMode);
      } catch (error) {
        setModeActionError(String(error instanceof Error ? error.message : error));
      } finally {
        setModeActionPending(false);
      }
    },
    [
      endOfWeekIso,
      loadModeData,
      startOfWeekIso,
      toIsoEnd,
      toIsoStart,
      user,
      weeklyDraft.p1,
      weeklyDraft.p2,
      weeklyDraft.p3,
    ],
  );

  const handleRetroCreate = useCallback(
    async (refreshMode: "retrobox" | "ritual" = "retrobox", weekStartIso?: string): Promise<void> => {
      if (!user) {
        return;
      }
      const content = retroDraft.content.trim();
      if (!content) {
        setModeActionError("Retrospective content is required.");
        setModeActionMessage("");
        return;
      }
      setModeActionPending(true);
      setModeActionError("");
      setModeActionMessage("");
      try {
        await createRetrospectiveMutation({
          actor_username: user.username,
          user_id: user.id,
          cycle_id: parsedCycleId || undefined,
          week_start_date: toIsoStart(weekStartIso || startOfWeekIso()),
          content,
          sentiment: retroDraft.sentiment.trim() || undefined,
        });
        setRetroDraft({ content: "", sentiment: "" });
        setModeActionMessage("Retrospective added.");
        await loadModeData(user, refreshMode);
      } catch (error) {
        setModeActionError(String(error instanceof Error ? error.message : error));
      } finally {
        setModeActionPending(false);
      }
    },
    [
      loadModeData,
      parsedCycleId,
      retroDraft.content,
      retroDraft.sentiment,
      setRetroDraft,
      startOfWeekIso,
      toIsoStart,
      user,
    ],
  );

  return {
    modeActionPending,
    modeActionMessage,
    modeActionError,
    handleWeeklyPlanSave,
    handleRetroCreate,
  };
}
