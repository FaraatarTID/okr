"use client";

import { useCallback, useEffect, useRef, useState, type Dispatch, type SetStateAction } from "react";

import { readBackendQuery, type AuthUser } from "@/lib/api";
import { endOfWeekIso, reviewWindow, startOfWeekIso, toDateInputValue } from "@/components/atlas-shell/shellDateUtils";

export type WeeklyPlanRead = {
  id: number;
  user_id: number;
  week_start_date: string;
  week_end_date: string;
  priority_1: string;
  priority_2?: string | null;
  priority_3?: string | null;
  is_active: boolean;
};

export type WorkLogRead = {
  id: number;
  task_id?: number | null;
  duration_minutes?: number | null;
  start_time?: string | null;
  end_time?: string | null;
  summary?: string | null;
  task?: { title?: string | null } | null;
};

export type KeyResultRead = {
  id: number;
  title?: string | null;
  progress?: number | null;
  current_value?: number | null;
  target_value?: number | null;
  start_value?: number | null;
  unit?: string | null;
  metric_type?: string | null;
  objective?: { title?: string | null } | null;
};

export type ExperimentRead = {
  id: number;
  key_result_id: number;
  cycle_id: number;
  created_by?: string | null;
  hypothesis?: string | null;
  change_description?: string | null;
  status?: "PLANNED" | "RUNNING" | "DECIDED" | null;
  start_at?: string | null;
  end_at?: string | null;
  created_at?: string | null;
  decision?: "ADOPT" | "ITERATE" | "REVERT" | "UNKNOWN" | null;
  decision_rationale?: string | null;
  expected_effect_direction?: "UP" | "DOWN" | null;
  expected_effect_size?: number | null;
};

export type RetroRead = {
  id: number;
  week_start_date?: string | null;
  content?: string | null;
  sentiment?: string | null;
  created_at?: string | null;
};

export type TimelineTaskRead = {
  id: number;
  title?: string | null;
  description?: string | null;
  progress?: number | null;
  status?: string | null;
  start_date?: string | null;
  deadline?: string | null;
  created_at?: string | null;
  assignee_id?: number | null;
  estimated_minutes?: number | null;
  key_result?: {
    title?: string | null;
    objective?: {
      title?: string | null;
      goal?: {
        title?: string | null;
        owner_id?: number | null;
      } | null;
    } | null;
  } | null;
};

type UseAtlasModeDataInput = {
  mode: string;
  user: AuthUser | null;
  parsedCycleId: number | null;
  setWeeklyDraft: Dispatch<SetStateAction<{ p1: string; p2: string; p3: string }>>;
  setRetroDraft: Dispatch<SetStateAction<{ content: string; sentiment: string }>>;
  loadLeadershipMetricsSnapshot: (activeUser: AuthUser) => Promise<unknown>;
};

const DASHBOARD_REFRESH_INTERVAL_MS = 30_000;

export default function useAtlasModeData({
  mode,
  user,
  parsedCycleId,
  setWeeklyDraft,
  setRetroDraft,
  loadLeadershipMetricsSnapshot,
}: UseAtlasModeDataInput) {
  const [modeDataPending, setModeDataPending] = useState(false);
  const [modeDataError, setModeDataError] = useState("");
  const [weeklyPlanData, setWeeklyPlanData] = useState<WeeklyPlanRead | null>(null);
  const [weeklyLogs, setWeeklyLogs] = useState<WorkLogRead[]>([]);
  const [weeklyKrsNeedingCheckIn, setWeeklyKrsNeedingCheckIn] = useState<KeyResultRead[]>([]);
  const [weeklyReviewExperiments, setWeeklyReviewExperiments] = useState<ExperimentRead[]>([]);
  const [dailyLogs, setDailyLogs] = useState<WorkLogRead[]>([]);
  const [ritualKrs, setRitualKrs] = useState<KeyResultRead[]>([]);
  const [ritualExperimentsByKr, setRitualExperimentsByKr] = useState<Record<number, ExperimentRead[]>>({});
  const [ritualReviewExperiments, setRitualReviewExperiments] = useState<ExperimentRead[]>([]);
  const [ritualReviewLogs, setRitualReviewLogs] = useState<WorkLogRead[]>([]);
  const [retroItems, setRetroItems] = useState<RetroRead[]>([]);
  const [timelineTasks, setTimelineTasks] = useState<TimelineTaskRead[]>([]);
  const [timelineLogs, setTimelineLogs] = useState<WorkLogRead[]>([]);
  const dashboardRefreshInFlightRef = useRef(false);

  const loadModeData = useCallback(
    async (activeUser: AuthUser, nextMode: string): Promise<void> => {
      if (nextMode === "atlas" || nextMode === "admin") {
        return;
      }
      setModeDataPending(true);
      setModeDataError("");
      try {
        if (nextMode === "weekly") {
          const weekStart = `${startOfWeekIso()}T00:00:00`;
          const weekEnd = `${endOfWeekIso()}T23:59:59`;
          const tasks: Array<Promise<Record<string, unknown>>> = [
            readBackendQuery({
              actor_username: activeUser.username,
              kind: "weekly_plan.active",
              params: { user_id: activeUser.id, date: new Date().toISOString() },
            }),
            readBackendQuery({
              actor_username: activeUser.username,
              kind: "work_logs.by_range",
              params: {
                user_id: activeUser.id,
                start_date: new Date(weekStart).toISOString(),
                end_date: new Date(weekEnd).toISOString(),
              },
            }),
          ];
          if (parsedCycleId) {
            tasks.push(
              readBackendQuery({
                actor_username: activeUser.username,
                kind: "krs.needing_checkin",
                params: {
                  user_id: activeUser.username,
                  cycle_id: parsedCycleId,
                  days_threshold: 7,
                },
              }),
            );
            const review = reviewWindow();
            tasks.push(
              readBackendQuery({
                actor_username: activeUser.username,
                kind: "experiments.for_retro_window",
                params: {
                  cycle_id: parsedCycleId,
                  window_start: review.start.toISOString(),
                  window_end: review.end.toISOString(),
                },
              }),
            );
          }
          const responses = await Promise.all(tasks);
          const planPayload = responses[0] || {};
          const logsPayload = responses[1] || {};
          const krsPayload = responses[2] || {};
          const experimentsPayload = responses[3] || {};
          const plan = (planPayload.weekly_plan as WeeklyPlanRead | null) || null;
          setWeeklyPlanData(plan);
          setWeeklyDraft({
            p1: String(plan?.priority_1 || ""),
            p2: String(plan?.priority_2 || ""),
            p3: String(plan?.priority_3 || ""),
          });
          setWeeklyLogs(((logsPayload.work_logs as WorkLogRead[]) || []).slice(0, 300));
          setWeeklyKrsNeedingCheckIn(((krsPayload.key_results as KeyResultRead[]) || []).slice(0, 120));
          setWeeklyReviewExperiments(
            ((experimentsPayload.experiments as ExperimentRead[]) || []).slice(0, 120),
          );
        } else if (nextMode === "daily") {
          const start = new Date();
          start.setHours(0, 0, 0, 0);
          const end = new Date();
          end.setHours(23, 59, 59, 999);
          const payload = await readBackendQuery({
            actor_username: activeUser.username,
            kind: "work_logs.by_range",
            params: {
              user_id: activeUser.id,
              start_date: start.toISOString(),
              end_date: end.toISOString(),
            },
          });
          setDailyLogs(((payload.work_logs as WorkLogRead[]) || []).slice(0, 100));
        } else if (nextMode === "ritual") {
          if (!parsedCycleId) {
            setRitualKrs([]);
            setRitualExperimentsByKr({});
            setRitualReviewExperiments([]);
            setRitualReviewLogs([]);
          } else {
            const review = reviewWindow();
            const ritualPayload = await readBackendQuery({
              actor_username: activeUser.username,
              kind: "ritual.snapshot",
              params: {
                user_id: activeUser.id,
                cycle_id: parsedCycleId,
                days_threshold: 7,
                date: new Date().toISOString(),
                window_start: review.start.toISOString(),
                window_end: review.end.toISOString(),
              },
            });
            const krPayload = { key_results: ritualPayload.key_results };
            const weeklyPayload = { weekly_plan: ritualPayload.weekly_plan };
            const retroPayload = { retros: ritualPayload.retros };
            const logsPayload = { work_logs: ritualPayload.work_logs };
            const experimentReviewPayload = { experiments: ritualPayload.experiments };
            const krs = ((krPayload.key_results as KeyResultRead[]) || []).slice(0, 100);
            setRitualKrs(krs);

            const plan = (weeklyPayload.weekly_plan as WeeklyPlanRead | null) || null;
            setWeeklyPlanData(plan);
            setWeeklyDraft({
              p1: String(plan?.priority_1 || ""),
              p2: String(plan?.priority_2 || ""),
              p3: String(plan?.priority_3 || ""),
            });

            const retros = ((retroPayload.retros as RetroRead[]) || []).slice(0, 50);
            setRetroItems(retros);
            const activeWeekStart = startOfWeekIso();
            const activeWeekRetro = retros.find(
              (item) => toDateInputValue(item.week_start_date) === activeWeekStart,
            );
            if (activeWeekRetro) {
              setRetroDraft((prev) => ({
                content: prev.content.trim() ? prev.content : String(activeWeekRetro.content || ""),
                sentiment:
                  prev.sentiment.trim() || String(activeWeekRetro.sentiment || ""),
              }));
            }

            setRitualReviewLogs(((logsPayload.work_logs as WorkLogRead[]) || []).slice(0, 200));
            setRitualReviewExperiments(
              ((experimentReviewPayload.experiments as ExperimentRead[]) || []).slice(0, 100),
            );

            const experimentResults = await Promise.allSettled(
              krs.map(async (kr) => {
                const krId = Number(kr.id);
                if (!Number.isFinite(krId) || krId <= 0) {
                  return [0, [] as ExperimentRead[]] as const;
                }
                const payload = await readBackendQuery({
                  actor_username: activeUser.username,
                  kind: "experiments.for_kr",
                  params: { key_result_id: krId },
                });
                return [krId, ((payload.experiments as ExperimentRead[]) || []).slice(0, 50)] as const;
              }),
            );
            const experimentsByKr: Record<number, ExperimentRead[]> = {};
            for (const result of experimentResults) {
              if (result.status !== "fulfilled") {
                continue;
              }
              const [krId, experiments] = result.value;
              if (!krId) {
                continue;
              }
              experimentsByKr[krId] = experiments;
            }
            setRitualExperimentsByKr(experimentsByKr);
          }
        } else if (nextMode === "retrobox") {
          const payload = await readBackendQuery({
            actor_username: activeUser.username,
            kind: "retros.user",
            params: {
              user_id: activeUser.id,
              cycle_id: parsedCycleId || undefined,
            },
          });
          setRetroItems(((payload.retros as RetroRead[]) || []).slice(0, 50));
        } else if (nextMode === "timeline" || nextMode === "dashboard") {
          const start = new Date();
          start.setDate(start.getDate() - 30);
          start.setHours(0, 0, 0, 0);
          const end = new Date();
          end.setHours(23, 59, 59, 999);
          const [tasksPayload, logsPayload] = await Promise.all([
            parsedCycleId
              ? readBackendQuery({
                  actor_username: activeUser.username,
                  kind: "tasks.by_cycle",
                  params: { cycle_id: parsedCycleId, limit: 500, offset: 0 },
                })
              : Promise.resolve({ tasks: [] as Record<string, unknown>[] }),
            readBackendQuery({
              actor_username: activeUser.username,
              kind: "work_logs.by_range",
              params: {
                user_id: activeUser.id,
                start_date: start.toISOString(),
                end_date: end.toISOString(),
              },
            }),
          ]);
          setTimelineTasks((tasksPayload.tasks as TimelineTaskRead[]) || []);
          setTimelineLogs((logsPayload.work_logs as WorkLogRead[]) || []);
          if (nextMode === "dashboard") {
            await loadLeadershipMetricsSnapshot(activeUser);
          }
        }
      } catch (error) {
        setModeDataError(String(error instanceof Error ? error.message : error));
      } finally {
        setModeDataPending(false);
      }
    },
    [loadLeadershipMetricsSnapshot, parsedCycleId, setRetroDraft, setWeeklyDraft],
  );

  const refreshDashboardModeData = useCallback(
    async (activeUser: AuthUser, activeMode: string): Promise<void> => {
      if (activeMode !== "dashboard" && activeMode !== "timeline") {
        return;
      }
      if (dashboardRefreshInFlightRef.current) {
        return;
      }
      dashboardRefreshInFlightRef.current = true;
      try {
        await loadModeData(activeUser, activeMode);
      } finally {
        dashboardRefreshInFlightRef.current = false;
      }
    },
    [loadModeData],
  );

  const appendRitualExperiment = useCallback((krId: number, experiment: ExperimentRead): void => {
    setRitualExperimentsByKr((prev) => {
      const existing = prev[krId] || [];
      return {
        ...prev,
        [krId]: [experiment, ...existing],
      };
    });
  }, []);

  useEffect(() => {
    if (!user || mode === "atlas" || mode === "admin") {
      return;
    }
    void loadModeData(user, mode);
  }, [loadModeData, mode, user]);

  useEffect(() => {
    if (!user || (mode !== "dashboard" && mode !== "timeline")) {
      return;
    }

    let active = true;

    const refreshFromSignal = () => {
      if (!active || modeDataPending) {
        return;
      }
      if (typeof document !== "undefined" && document.hidden) {
        return;
      }
      void refreshDashboardModeData(user, mode);
    };

    const pollTimer = window.setInterval(refreshFromSignal, DASHBOARD_REFRESH_INTERVAL_MS);
    window.addEventListener("focus", refreshFromSignal);
    document.addEventListener("visibilitychange", refreshFromSignal);

    return () => {
      active = false;
      window.clearInterval(pollTimer);
      window.removeEventListener("focus", refreshFromSignal);
      document.removeEventListener("visibilitychange", refreshFromSignal);
    };
  }, [mode, modeDataPending, refreshDashboardModeData, user]);

  return {
    modeDataPending,
    modeDataError,
    weeklyPlanData,
    weeklyLogs,
    weeklyKrsNeedingCheckIn,
    weeklyReviewExperiments,
    dailyLogs,
    ritualKrs,
    ritualExperimentsByKr,
    ritualReviewExperiments,
    ritualReviewLogs,
    retroItems,
    timelineTasks,
    timelineLogs,
    loadModeData,
    refreshDashboardModeData,
    appendRitualExperiment,
  };
}
