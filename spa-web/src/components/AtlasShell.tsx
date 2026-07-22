"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import {
  atlasRollup,
  buildAtlasIndexFromSnapshot,
  flattenScopeRefs,
  nodeTypeLabel,
  type AtlasIndexNode,
  type AtlasKeyResultSnapshot,
  type AtlasObjectiveSnapshot,
  type AtlasTaskSnapshot,
} from "@/lib/atlas";
import {
  type CycleSummary,
} from "@/lib/api";
import {
  DEFAULT_LENS,
  DEFAULT_MODE,
  buildDeepLinkQuery,
  normalizeFocusTaskRef,
} from "@/lib/deeplink";
import {
  SIDEBAR_ITEMS,
  modeDisplayLabel,
} from "@/components/atlas-shell/navigation";
import {
  createTypeLabel,
  nearestAncestorId,
} from "@/components/atlas-shell/nodeMutation";
import { selectedNodeDetails } from "@/components/atlas-shell/inspectorDetails";
import AdminModePanel, {
  type AdminTab,
} from "@/components/atlas-shell/AdminModePanel";
import DashboardLeadershipPanel from "@/components/atlas-shell/DashboardLeadershipPanel";
import TimelineModePanel from "@/components/atlas-shell/TimelineModePanel";
import WeeklyModePanel from "@/components/atlas-shell/WeeklyModePanel";
import DailyModePanel from "@/components/atlas-shell/DailyModePanel";
import RitualModePanel from "@/components/atlas-shell/RitualModePanel";
import RetroboxModePanel from "@/components/atlas-shell/RetroboxModePanel";
import AtlasFocusMapPanel from "@/components/atlas-shell/AtlasFocusMapPanel";
import AtlasModeControlsPanel from "@/components/atlas-shell/AtlasModeControlsPanel";
import InspectorAiAssistPanel from "@/components/atlas-shell/InspectorAiAssistPanel";
import InspectorEditAnalysisPanel from "@/components/atlas-shell/InspectorEditAnalysisPanel";
import InspectorManageNodesPanel from "@/components/atlas-shell/InspectorManageNodesPanel";
import InspectorTaskWorkHistoryPanel from "@/components/atlas-shell/InspectorTaskWorkHistoryPanel";
import InspectorAlignmentPanel from "@/components/atlas-shell/InspectorAlignmentPanel";
import useInspectorAuxData from "@/components/atlas-shell/useInspectorAuxData";
import useLeadershipInsights from "@/components/atlas-shell/useLeadershipInsights";
import useAtlasModeData from "@/components/atlas-shell/useAtlasModeData";
import useReportGeneration from "@/components/atlas-shell/useReportGeneration";
import useTimerSession from "@/components/atlas-shell/useTimerSession";
import useAiProgressAssist from "@/components/atlas-shell/useAiProgressAssist";
import useInspectorNodeActions from "@/components/atlas-shell/useInspectorNodeActions";
import useRitualActions from "@/components/atlas-shell/useRitualActions";
import useAdminActions from "@/components/atlas-shell/useAdminActions";
import useAdminResources from "@/components/atlas-shell/useAdminResources";
import useModeActions from "@/components/atlas-shell/useModeActions";
import useMindmapData from "@/components/atlas-shell/useMindmapData";
import useAuthBootstrap from "@/components/atlas-shell/useAuthBootstrap";
import useSnapshotLifecycle from "@/components/atlas-shell/useSnapshotLifecycle";
import useDeepLinkCycleBootstrap from "@/components/atlas-shell/useDeepLinkCycleBootstrap";
import useAtlasNavigation from "@/components/atlas-shell/useAtlasNavigation";
import useSelectionFocusSync from "@/components/atlas-shell/useSelectionFocusSync";
import useShellAccessControl from "@/components/atlas-shell/useShellAccessControl";
import useModeStateReset from "@/components/atlas-shell/useModeStateReset";
import {
  addDays,
  endOfDay,
  endOfWeekIso,
  formatElapsedClock,
  formatOptionalDate,
  formatOptionalNumber,
  parseDateOrNull,
  reviewWindow,
  startOfDay,
  startOfWeekIso,
  toDateInputValue,
  toDateShortLabel,
  toIsoEnd,
  toIsoStart,
} from "@/components/atlas-shell/shellDateUtils";
import {
  asRecord,
  averageLogMinutes,
  clampProgress,
  formatSignedDelta,
  groupLogsByTask,
  parseNumberOrNull,
  sumLogMinutes,
} from "@/components/atlas-shell/shellAnalyticsUtils";
import {
  buildMindmapTree,
  findMindmapNodeTitle,
  isGenericIndexedTitle,
  type MindmapTreeNode,
} from "@/components/atlas-shell/shellMindmapUtils";
import {
  cycleDisplayLabel,
  normalizeTaskStatus,
  parseOwnerIds,
  cyclePeriodLabel,
  timelineStatusLabel,
} from "@/components/atlas-shell/shellUiUtils";

type ResolvedCycle = Pick<CycleSummary, "id" | "title" | "start_date" | "end_date">;
type WeeklyPlanRead = {
  id: number;
  user_id: number;
  week_start_date: string;
  week_end_date: string;
  priority_1: string;
  priority_2?: string | null;
  priority_3?: string | null;
  is_active: boolean;
};
type WorkLogRead = {
  id: number;
  task_id?: number | null;
  duration_minutes?: number | null;
  start_time?: string | null;
  end_time?: string | null;
  summary?: string | null;
  task?: { title?: string | null } | null;
};
type RetroRead = {
  id: number;
  week_start_date?: string | null;
  content?: string | null;
  sentiment?: string | null;
  created_at?: string | null;
};
type TimelineTaskRead = {
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

type TimelineRow = {
  id: number;
  title: string;
  status: string;
  progress: number;
  assigneeName: string;
  keyResultTitle: string;
  objectiveTitle: string;
  goalTitle: string;
  startAt: Date;
  endAt: Date;
  isProjectedEnd: boolean;
  isOverdue: boolean;
};

const TYPE_TAG: Record<AtlasIndexNode["type"], string> = {
  GOAL: "G",
  OBJECTIVE: "O",
  KEY_RESULT: "KR",
  TASK: "T",
};

export default function AtlasShell() {
  const router = useRouter();
  const [cycleId, setCycleId] = useState("");
  const [resolvedCycle, setResolvedCycle] = useState<ResolvedCycle | null>(null);
  const [cycleResolvePending, setCycleResolvePending] = useState(false);
  const [cycleResolveError, setCycleResolveError] = useState("");
  const [sessionCycles, setSessionCycles] = useState<CycleSummary[]>([]);
  const [adminTab, setAdminTab] = useState<AdminTab>("cycles");
  const [mode, setMode] = useState(DEFAULT_MODE);
  const [dailyLogQuery, setDailyLogQuery] = useState("");
  const [ritualStep, setRitualStep] = useState<1 | 2 | 3>(1);
  const [timelineQuery, setTimelineQuery] = useState("");
  const [timelineStatusFilter, setTimelineStatusFilter] = useState<
    "all" | "todo" | "in_progress" | "done" | "blocked" | "overdue"
  >("all");
  const [weeklyDraft, setWeeklyDraft] = useState({ p1: "", p2: "", p3: "" });
  const [retroDraft, setRetroDraft] = useState({ content: "", sentiment: "" });
  const [lens, setLens] = useState(DEFAULT_LENS);
  const [ownerIdsInput, setOwnerIdsInput] = useState("");
  const [nodeQuery, setNodeQuery] = useState("");
  const [selectedRef, setSelectedRef] = useState("");
  const [focusTaskRef, setFocusTaskRef] = useState("");
  const [deepLinkReady, setDeepLinkReady] = useState(false);
  const { user, setUser, authHydrated } = useAuthBootstrap();

  const isAdmin = String(user?.role || "").trim().toLowerCase() === "admin";
  const isManager = String(user?.role || "").trim().toLowerCase() === "manager";
  const canManageCycleSelection = isAdmin || isManager;
  const ritualReviewRange = useMemo(() => reviewWindow(), []);
  const effectiveCycleId = canManageCycleSelection
    ? cycleId
    : (resolvedCycle?.id ? String(resolvedCycle.id) : "");
  const parsedCycleId = useMemo(() => {
    const parsed = Number.parseInt(effectiveCycleId, 10);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  }, [effectiveCycleId]);
  const effectiveOwnerIdsInput = isAdmin ? ownerIdsInput : "";
  const parsedOwnerIds = useMemo(() => parseOwnerIds(effectiveOwnerIdsInput), [effectiveOwnerIdsInput]);
  const selectedOwnerIds = parsedOwnerIds.value || [];
  const {
    snapshotPending,
    snapshotError,
    snapshotPayload,
    snapshotPollIntervalMs,
    clearSnapshot,
    loadSnapshotForUser,
  } = useSnapshotLifecycle({
    user,
    mode,
    parsedCycleId,
    ownerIds: parsedOwnerIds.value,
    ownerIdsError: parsedOwnerIds.error,
  });
  const {
    leadershipMetrics,
    leadershipPending,
    leadershipError,
    teamCoachPending,
    teamCoachError,
    teamCoachSummary,
    strategyPulsePending,
    strategyPulseError,
    strategyPulseSummary,
    loadLeadershipMetricsSnapshot,
    handleGenerateTeamCoachSummary,
    handleGenerateStrategyPulseSummary,
  } = useLeadershipInsights({
    mode,
    user,
    parsedCycleId,
    cycleLabel: cycleDisplayLabel(resolvedCycle),
  });
  const {
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
  } = useAtlasModeData({
    mode,
    user,
    parsedCycleId,
    setWeeklyDraft,
    setRetroDraft,
    loadLeadershipMetricsSnapshot,
  });
  const {
    modeActionPending,
    modeActionMessage,
    modeActionError,
    handleWeeklyPlanSave,
    handleRetroCreate,
  } = useModeActions({
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
  });
  const {
    ritualCheckInDrafts,
    ritualExperimentDrafts,
    ritualExperimentFormOpen,
    setRitualExperimentFormOpen,
    ritualExperimentPending,
    ritualExperimentError,
    ritualExperimentMessage,
    ritualExperimentCloseDrafts,
    ritualExperimentActionPending,
    updateRitualExperimentCloseDraft,
    ritualExperimentActionError,
    ritualExperimentActionMessage,
    updateRitualCheckInDraft,
    updateRitualExperimentDraft,
    handleRitualExperimentCreate,
    handleRitualExperimentStart,
    handleRitualExperimentClose,
    ritualCheckInPending,
    handleRitualCheckInSubmit,
    ritualCheckInError,
    ritualCheckInMessage,
  } = useRitualActions({
    user,
    parsedCycleId,
    ritualKrs,
    ritualExperimentsByKr,
    loadModeData,
    loadSnapshotForUser,
    appendRitualExperiment,
  });
  const {
    adminCycles,
    adminCyclesPending,
    adminUsers,
    adminTeams,
    setAdminTeams,
    adminDataPending,
    adminCycleError,
    setAdminCycleError,
    adminDataError,
    setAdminDataError,
    adminAiHealth,
    adminPdfHealth,
    adminHealthPending,
    adminAuditSummary,
    adminAuditSummaryPending,
    adminAuditSummaryError,
    loadAdminCycles,
    loadAdminUsersAndTeams,
    loadAdminResources,
    loadAdminHealth,
    loadAdminAuditSummary,
  } = useAdminResources();
  const ownerFilterOptions = useMemo(() => {
    const deduped = new Map<number, string>();
    if (user?.id && user.id > 0) {
      const selfLabel = String(user.display_name || user.username || `User #${user.id}`).trim();
      deduped.set(user.id, selfLabel || `User #${user.id}`);
    }
    for (const adminUser of adminUsers) {
      const userId = Number(adminUser.id);
      if (!Number.isFinite(userId) || userId <= 0) {
        continue;
      }
      const displayName = String(adminUser.display_name || "").trim();
      const username = String(adminUser.username || "").trim();
      deduped.set(userId, displayName || username || `User #${userId}`);
    }
    const usersMap = snapshotPayload?.users_map || {};
    for (const [key, value] of Object.entries(usersMap)) {
      const userId = Number.parseInt(String(key), 10);
      if (!Number.isFinite(userId) || userId <= 0) {
        continue;
      }
      const label = String(value || "").trim() || `User #${userId}`;
      if (!deduped.has(userId)) {
        deduped.set(userId, label);
      }
    }
    return Array.from(deduped.entries())
      .map(([id, label]) => ({ id, label }))
      .sort((left, right) => left.label.localeCompare(right.label));
  }, [adminUsers, snapshotPayload, user]);
  const cycleOptions = useMemo(() => {
    const ownerScopedCycles =
      selectedOwnerIds.length > 0
        ? sessionCycles.filter((cycle) => {
            const ownerId = Number(cycle.owner_manager_id);
            return Number.isFinite(ownerId) && ownerId > 0 && selectedOwnerIds.includes(ownerId);
          })
        : sessionCycles;
    const deduped = new Map<number, string>();
    for (const cycle of ownerScopedCycles) {
      const cycleIdValue = Number(cycle.id);
      if (!Number.isFinite(cycleIdValue) || cycleIdValue <= 0) {
        continue;
      }
      const period = cyclePeriodLabel(cycle);
      const title = String(cycle.title || "").trim() || `Cycle ${cycleIdValue}`;
      deduped.set(cycleIdValue, period ? `${title} (${period})` : title);
    }
    if (selectedOwnerIds.length === 0 && resolvedCycle?.id && !deduped.has(resolvedCycle.id)) {
      const period = cyclePeriodLabel(resolvedCycle);
      const title = String(resolvedCycle.title || "").trim() || `Cycle ${resolvedCycle.id}`;
      deduped.set(resolvedCycle.id, period ? `${title} (${period})` : title);
    }
    return Array.from(deduped.entries())
      .map(([id, label]) => ({ id, label }))
      .sort((left, right) => right.id - left.id);
  }, [resolvedCycle, selectedOwnerIds, sessionCycles]);
  const {
    adminCycleMessage,
    setAdminCycleMessage,
    adminUserDraft,
    setAdminUserDraft,
    adminTeamDraft,
    setAdminTeamDraft,
    adminResetDraft,
    setAdminResetDraft,
    adminBackupFile,
    setAdminBackupFile,
    adminBackupConfirm,
    setAdminBackupConfirm,
    adminBackupRestoreResult,
    setAdminBackupRestoreResult,
    adminBackupPending,
    adminCreateCycleDraft,
    setAdminCreateCycleDraft,
    handleAdminBackupExport,
    handleAdminBackupRestore,
    handleAdminCreateUser,
    handleAdminToggleUserActive,
    handleAdminCreateTeam,
    handleAdminUpdateTeam,
    handleAdminDeleteTeam,
    handleAdminResetPassword,
    handleAdminCreateCycle,
    handleAdminSetCycleActive,
    handleAdminUpdateCycleOwner,
    handleAdminDeleteCycle,
  } = useAdminActions({
    user,
    isAdmin,
    adminUsers,
    setAdminCycleError,
    setAdminDataError,
    loadAdminCycles,
    loadAdminUsersAndTeams,
    loadAdminResources,
    onCycleActivated: (cycle) => {
      setResolvedCycle({
        id: cycle.id,
        title: cycle.title,
        start_date: cycle.start_date || null,
        end_date: cycle.end_date || null,
      });
      setCycleId(String(cycle.id));
    },
    toIsoStart,
    toIsoEnd,
  });
  const {
    reportExportPending,
    reportExportError,
    reportAiPending,
    reportAiError,
    reportAiSummary,
    handleReportExport,
    handleReportAiSummaryGenerate,
  } = useReportGeneration({
    user,
    mode,
    parsedCycleId,
    formatOptionalDate,
  });

  useModeStateReset({
    mode,
    setTimelineQuery,
    setTimelineStatusFilter,
    setDailyLogQuery,
    setRitualStep,
  });

  const atlasRuntime = useMemo(() => {
    if (!snapshotPayload) {
      return null;
    }
    return buildAtlasIndexFromSnapshot(snapshotPayload);
  }, [snapshotPayload]);

  const rollup = useMemo(() => {
    if (!atlasRuntime) {
      return null;
    }
    return atlasRollup(atlasRuntime.index);
  }, [atlasRuntime]);

  const allScopeRefs = useMemo(() => {
    if (!atlasRuntime) {
      return [];
    }
    return flattenScopeRefs(atlasRuntime.roots, atlasRuntime.index);
  }, [atlasRuntime]);

  const taskRefs = useMemo(() => {
    if (!atlasRuntime) {
      return [];
    }
    return allScopeRefs.filter((ref) => atlasRuntime.index[ref]?.type === "TASK");
  }, [allScopeRefs, atlasRuntime]);

  const timelineRows = useMemo<TimelineRow[]>(() => {
    if (!timelineTasks.length) {
      return [];
    }
    const usersMap = snapshotPayload?.users_map || {};
    const now = new Date();
    return timelineTasks
      .map((task): TimelineRow | null => {
        const taskId = Number(task.id);
        if (!Number.isFinite(taskId) || taskId <= 0) {
          return null;
        }
        const start = parseDateOrNull(task.start_date) || parseDateOrNull(task.created_at);
        if (!start) {
          return null;
        }
        const deadline = parseDateOrNull(task.deadline);
        const end = deadline || addDays(start, 1);
        const safeEnd = end.getTime() <= start.getTime() ? addDays(start, 1) : end;
        const status = normalizeTaskStatus(task.status);
        const assigneeId = Number(task.assignee_id);
        const assigneeName =
          Number.isFinite(assigneeId) && assigneeId > 0
            ? String(usersMap[String(assigneeId)] || `User #${assigneeId}`)
            : "Unassigned";
        return {
          id: taskId,
          title: String(task.title || `Task #${taskId}`),
          status,
          progress: clampProgress(task.progress),
          assigneeName,
          keyResultTitle: String(task.key_result?.title || ""),
          objectiveTitle: String(task.key_result?.objective?.title || ""),
          goalTitle: String(task.key_result?.objective?.goal?.title || ""),
          startAt: start,
          endAt: safeEnd,
          isProjectedEnd: !deadline,
          isOverdue: status !== "DONE" && safeEnd.getTime() < now.getTime(),
        };
      })
      .filter((row): row is TimelineRow => Boolean(row))
      .sort((left, right) => left.startAt.getTime() - right.startAt.getTime());
  }, [timelineTasks, snapshotPayload]);

  const timelineWindow = useMemo(() => {
    if (!timelineRows.length) {
      return null;
    }
    let minStart = timelineRows[0].startAt.getTime();
    let maxEnd = timelineRows[0].endAt.getTime();
    for (const row of timelineRows) {
      const startMs = row.startAt.getTime();
      const endMs = row.endAt.getTime();
      if (startMs < minStart) {
        minStart = startMs;
      }
      if (endMs > maxEnd) {
        maxEnd = endMs;
      }
    }
    const start = startOfDay(addDays(new Date(minStart), -1));
    const end = endOfDay(addDays(new Date(maxEnd), 1));
    const spanMs = Math.max(1, end.getTime() - start.getTime());
    const now = Date.now();
    const todayLeftPct = Math.max(0, Math.min(100, ((now - start.getTime()) / spanMs) * 100));
    return { start, end, spanMs, todayLeftPct };
  }, [timelineRows]);

  const timelineStatusCounts = useMemo(() => {
    const totals = {
      todo: 0,
      inProgress: 0,
      done: 0,
      blocked: 0,
      overdue: 0,
    };
    for (const row of timelineRows) {
      if (row.status === "DONE") {
        totals.done += 1;
      } else if (row.status === "IN_PROGRESS") {
        totals.inProgress += 1;
      } else if (row.status === "BLOCKED") {
        totals.blocked += 1;
      } else {
        totals.todo += 1;
      }
      if (row.isOverdue) {
        totals.overdue += 1;
      }
    }
    return totals;
  }, [timelineRows]);

  const timelineRowsFiltered = useMemo(() => {
    const query = timelineQuery.trim().toLowerCase();
    return timelineRows.filter((row) => {
      if (timelineStatusFilter === "overdue" && !row.isOverdue) {
        return false;
      }
      if (
        timelineStatusFilter !== "all" &&
        timelineStatusFilter !== "overdue" &&
        row.status.toLowerCase() !== timelineStatusFilter
      ) {
        return false;
      }
      if (!query) {
        return true;
      }
      const composite = [
        row.title,
        row.assigneeName,
        row.keyResultTitle,
        row.objectiveTitle,
        row.goalTitle,
        timelineStatusLabel(row.status),
      ]
        .join(" ")
        .toLowerCase();
      return composite.includes(query);
    });
  }, [timelineQuery, timelineRows, timelineStatusFilter]);

  const ritualSubmittedCount = useMemo(() => {
    if (!ritualKrs.length) {
      return 0;
    }
    return ritualKrs.reduce((count, kr) => {
      return ritualCheckInMessage[kr.id] ? count + 1 : count;
    }, 0);
  }, [ritualCheckInMessage, ritualKrs]);

  const dailyLogsFiltered = useMemo(() => {
    const query = dailyLogQuery.trim().toLowerCase();
    if (!query) {
      return dailyLogs;
    }
    return dailyLogs.filter((row) => {
      const text = [
        row.task?.title || "",
        row.summary || "",
        formatOptionalDate(row.start_time),
      ]
        .join(" ")
        .toLowerCase();
      return text.includes(query);
    });
  }, [dailyLogQuery, dailyLogs]);

  const dailyTotalMinutes = useMemo(() => sumLogMinutes(dailyLogsFiltered), [dailyLogsFiltered]);
  const dailyAverageMinutes = useMemo(
    () => averageLogMinutes(dailyLogsFiltered),
    [dailyLogsFiltered],
  );
  const dailyDeepWorkShare = useMemo(() => {
    if (!dailyLogsFiltered.length) {
      return 0;
    }
    const deepWorkSessions = dailyLogsFiltered.filter(
      (row) => Number(row.duration_minutes || 0) >= 45,
    ).length;
    return Math.round((deepWorkSessions / dailyLogsFiltered.length) * 100);
  }, [dailyLogsFiltered]);
  const dailyTopTasks = useMemo(() => groupLogsByTask(dailyLogsFiltered).slice(0, 5), [dailyLogsFiltered]);
  const dailyTimeBands = useMemo(() => {
    const bands = {
      morning: 0,
      afternoon: 0,
      evening: 0,
    };
    for (const row of dailyLogsFiltered) {
      const parsed = parseDateOrNull(row.start_time);
      const hour = parsed ? parsed.getHours() : null;
      const minutes = Math.round(Number(row.duration_minutes || 0));
      if (hour === null) {
        continue;
      }
      if (hour < 12) {
        bands.morning += minutes;
      } else if (hour < 18) {
        bands.afternoon += minutes;
      } else {
        bands.evening += minutes;
      }
    }
    return bands;
  }, [dailyLogsFiltered]);

  const weeklyTotalMinutes = useMemo(() => sumLogMinutes(weeklyLogs), [weeklyLogs]);
  const weeklyAverageMinutes = useMemo(() => averageLogMinutes(weeklyLogs), [weeklyLogs]);
  const weeklyTopTasks = useMemo(() => groupLogsByTask(weeklyLogs).slice(0, 6), [weeklyLogs]);
  const weeklyPriorityCoverage = useMemo(() => {
    const priorities = [weeklyPlanData?.priority_1, weeklyPlanData?.priority_2, weeklyPlanData?.priority_3];
    const filled = priorities.filter((item) => String(item || "").trim()).length;
    return { filled, total: 3, pct: Math.round((filled / 3) * 100) };
  }, [weeklyPlanData]);

  const dashboardCompletionPct = useMemo(() => {
    const total = timelineRows.length;
    if (!total) {
      return 0;
    }
    return Math.round((timelineStatusCounts.done / total) * 100);
  }, [timelineRows.length, timelineStatusCounts.done]);
  const dashboardRiskPressurePct = useMemo(() => {
    const total = Math.max(0, Number(leadershipMetrics?.total_krs || 0));
    const risk = Math.max(0, Number(leadershipMetrics?.at_risk_count || 0));
    if (!total) {
      return 0;
    }
    return Math.round((risk / total) * 100);
  }, [leadershipMetrics?.at_risk_count, leadershipMetrics?.total_krs]);
  const dashboardFocusMinutes30d = useMemo(() => sumLogMinutes(timelineLogs), [timelineLogs]);
  const dashboardAvgDailyFocus30d = useMemo(
    () => Math.round(dashboardFocusMinutes30d / 30),
    [dashboardFocusMinutes30d],
  );
  const dashboardTopTasks = useMemo(() => groupLogsByTask(timelineLogs).slice(0, 6), [timelineLogs]);
  const dashboardAtRiskRows = useMemo(() => {
    const rows = Array.isArray(leadershipMetrics?.at_risk) ? leadershipMetrics?.at_risk : [];
    return rows.slice(0, 6).map((row) => {
      const payload = asRecord(row) || {};
      return {
        title: String(payload.title || payload.kr_title || "Untitled KR"),
        reason: String(payload.reason || payload.risk_reason || "Needs review"),
        owner: String(payload.owner_username || payload.owner || "Unknown"),
      };
    });
  }, [leadershipMetrics?.at_risk]);

  const dashboardTrendDeltas = useMemo(() => {
    const now = Date.now();
    const recentStart = now - 15 * 24 * 60 * 60 * 1000;
    const historyStart = now - 30 * 24 * 60 * 60 * 1000;
    let recentMinutes = 0;
    let previousMinutes = 0;
    let recentSessions = 0;
    let previousSessions = 0;

    for (const log of timelineLogs) {
      const parsed = parseDateOrNull(log.start_time);
      if (!parsed) {
        continue;
      }
      const ts = parsed.getTime();
      if (ts < historyStart || ts > now) {
        continue;
      }
      const minutes = Math.round(Number(log.duration_minutes || 0));
      if (ts >= recentStart) {
        recentMinutes += minutes;
        recentSessions += 1;
      } else {
        previousMinutes += minutes;
        previousSessions += 1;
      }
    }

    const recentDone = timelineRows.filter(
      (row) => row.status === "DONE" && row.startAt.getTime() >= recentStart,
    ).length;
    const previousDone = timelineRows.filter(
      (row) =>
        row.status === "DONE" &&
        row.startAt.getTime() >= historyStart &&
        row.startAt.getTime() < recentStart,
    ).length;

    const minuteDelta = recentMinutes - previousMinutes;
    const sessionDelta = recentSessions - previousSessions;
    const doneDelta = recentDone - previousDone;
    const minuteDeltaPct = previousMinutes > 0 ? Math.round((minuteDelta / previousMinutes) * 100) : null;

    return {
      recentMinutes,
      previousMinutes,
      recentSessions,
      previousSessions,
      recentDone,
      previousDone,
      minuteDelta,
      sessionDelta,
      doneDelta,
      minuteDeltaPct,
    };
  }, [timelineLogs, timelineRows]);

  const dashboardOwnerLoad = useMemo(() => {
    const rows = new Map<
      string,
      {
        owner: string;
        total: number;
        active: number;
        blocked: number;
        overdue: number;
        completed: number;
      }
    >();
    for (const row of timelineRows) {
      const owner = String(row.assigneeName || "Unassigned");
      const bucket = rows.get(owner) || {
        owner,
        total: 0,
        active: 0,
        blocked: 0,
        overdue: 0,
        completed: 0,
      };
      bucket.total += 1;
      if (row.status === "DONE") {
        bucket.completed += 1;
      } else {
        bucket.active += 1;
      }
      if (row.status === "BLOCKED") {
        bucket.blocked += 1;
      }
      if (row.isOverdue) {
        bucket.overdue += 1;
      }
      rows.set(owner, bucket);
    }
    return [...rows.values()]
      .map((row) => ({
        ...row,
        pressureScore: row.active * 2 + row.blocked * 2 + row.overdue * 3,
      }))
      .sort((left, right) => {
        if (right.pressureScore !== left.pressureScore) {
          return right.pressureScore - left.pressureScore;
        }
        if (right.active !== left.active) {
          return right.active - left.active;
        }
        return right.total - left.total;
      })
      .slice(0, 8);
  }, [timelineRows]);

  const dashboardRiskDrilldown = useMemo(() => {
    const source = Array.isArray(leadershipMetrics?.at_risk) ? leadershipMetrics.at_risk : [];
    return source.slice(0, 8).map((raw, idx) => {
      const payload = asRecord(raw) || {};
      return {
        key: String(payload.id || payload.kr_id || payload.key_result_id || `${idx}`),
        title: String(payload.title || payload.kr_title || "Untitled KR"),
        owner: String(payload.owner_username || payload.owner || "Unknown"),
        reason: String(payload.reason || payload.risk_reason || "Needs review"),
        confidence: parseNumberOrNull(payload.confidence || payload.confidence_score),
        riskScore: parseNumberOrNull(payload.risk_score || payload.score || payload.risk_pct),
        deadline: String(payload.deadline || payload.due_date || payload.end_date || "").trim(),
        lagDays: parseNumberOrNull(payload.days_since_last_checkin || payload.check_in_age_days),
      };
    });
  }, [leadershipMetrics?.at_risk]);

  const deepLinkQuery = useMemo(() => {
    const baseQuery = buildDeepLinkQuery({
      cycle: effectiveCycleId,
      mode,
      sel: selectedRef,
      ft: focusTaskRef,
      lens,
    });
    const params = new URLSearchParams(baseQuery);
    return params.toString();
  }, [effectiveCycleId, mode, selectedRef, focusTaskRef, lens]);
  useDeepLinkCycleBootstrap({
    user,
    canManageCycleSelection,
    parsedCycleId,
    resolvedCycle,
    sessionCycles,
    deepLinkReady,
    deepLinkQuery,
    setResolvedCycle,
    setCycleResolvePending,
    setCycleResolveError,
    setSessionCycles,
    setCycleId,
    setMode,
    setLens,
    setSelectedRef,
    setFocusTaskRef,
    setDeepLinkReady,
  });
  const { handleSidebarModeSelect, handleOpenTaskInAtlas } = useAtlasNavigation({
    routerReplace: (href) => router.replace(href),
    cycleId: effectiveCycleId,
    selectedRef,
    focusTaskRef,
    lens,
    setMode,
    setSelectedRef,
    setFocusTaskRef,
  });

  const filteredRefs = useMemo(() => {
    if (!atlasRuntime) {
      return [];
    }
    const rankByLens = (ref: string): number => {
      const meta = atlasRuntime.index[ref];
      if (!meta) {
        return Number.NEGATIVE_INFINITY;
      }
      if (lens === "health") {
        let score = 0;
        const progressPenalty = Math.max(0, 100 - Math.max(0, Math.min(100, meta.progress)));
        if (meta.type === "TASK") {
          const task = meta.node as AtlasTaskSnapshot;
          const status = normalizeTaskStatus(task.status);
          if (status === "BLOCKED") {
            score += 80;
          } else if (status === "IN_PROGRESS") {
            score += 35;
          } else if (status === "TODO") {
            score += 45;
          }
          const deadline = parseDateOrNull(task.deadline);
          if (deadline && status !== "DONE") {
            const now = Date.now();
            const deltaMs = deadline.getTime() - now;
            if (deltaMs < 0) {
              score += 70;
            } else if (deltaMs <= 3 * 24 * 60 * 60 * 1000) {
              score += 35;
            }
          }
          score += progressPenalty * 0.45;
        } else if (meta.type === "KEY_RESULT") {
          const kr = meta.node as AtlasKeyResultSnapshot;
          const deadlineState = String(kr.ai_deadline_state || "").trim().toLowerCase();
          if (
            deadlineState.includes("overdue") ||
            deadlineState.includes("risk") ||
            deadlineState.includes("at_risk")
          ) {
            score += 60;
          }
          score += progressPenalty * 0.6;
        } else if (meta.type === "OBJECTIVE") {
          score += progressPenalty * 0.5;
        } else {
          score += progressPenalty * 0.4;
        }
        return score;
      }
      if (lens === "owner") {
        const ownerBucket = String(meta.ownerName || "").trim().toLowerCase();
        const ownerHash = ownerBucket
          .split("")
          .reduce((acc, ch) => (acc * 31 + ch.charCodeAt(0)) >>> 0, 0);
        return ownerHash;
      }
      return 0;
    };

    const query = nodeQuery.trim().toLowerCase();
    const base = allScopeRefs.filter((ref) => {
      const meta = atlasRuntime.index[ref];
      if (!meta) {
        return false;
      }
      if (!query) {
        return true;
      }
      return (
        meta.titleLower.includes(query) ||
        meta.description.toLowerCase().includes(query) ||
        meta.ownerName.toLowerCase().includes(query) ||
        meta.ref.includes(query)
      );
    });

    if (lens === "health") {
      return [...base].sort((left, right) => {
        const scoreDelta = rankByLens(right) - rankByLens(left);
        if (scoreDelta !== 0) {
          return scoreDelta;
        }
        const leftMeta = atlasRuntime.index[left];
        const rightMeta = atlasRuntime.index[right];
        const depthDelta = (leftMeta?.depth || 0) - (rightMeta?.depth || 0);
        if (depthDelta !== 0) {
          return depthDelta;
        }
        return String(leftMeta?.title || "").localeCompare(String(rightMeta?.title || ""));
      });
    }

    if (lens === "owner") {
      return [...base].sort((left, right) => {
        const leftMeta = atlasRuntime.index[left];
        const rightMeta = atlasRuntime.index[right];
        const ownerDelta = String(leftMeta?.ownerName || "").localeCompare(String(rightMeta?.ownerName || ""));
        if (ownerDelta !== 0) {
          return ownerDelta;
        }
        const depthDelta = (leftMeta?.depth || 0) - (rightMeta?.depth || 0);
        if (depthDelta !== 0) {
          return depthDelta;
        }
        return String(leftMeta?.title || "").localeCompare(String(rightMeta?.title || ""));
      });
    }

    return base;
  }, [allScopeRefs, atlasRuntime, lens, nodeQuery]);

  const selectedMeta = useMemo(() => {
    if (!atlasRuntime || !selectedRef) {
      return null;
    }
    return atlasRuntime.index[selectedRef] || null;
  }, [atlasRuntime, selectedRef]);
  const { mindmapPayload } = useMindmapData({ user, selectedMeta });

  const createContext = useMemo(() => {
    return {
      goalId: nearestAncestorId(selectedMeta, atlasRuntime?.index || null, "GOAL"),
      objectiveId: nearestAncestorId(selectedMeta, atlasRuntime?.index || null, "OBJECTIVE"),
      keyResultId: nearestAncestorId(selectedMeta, atlasRuntime?.index || null, "KEY_RESULT"),
    };
  }, [atlasRuntime, selectedMeta]);

  const sidebarItems = useMemo(
    () => (isAdmin ? SIDEBAR_ITEMS : SIDEBAR_ITEMS.filter((item) => item.mode !== "admin")),
    [isAdmin],
  );
  const {
    aiSyncPending,
    aiSyncError,
    aiSyncMessage,
    aiSyncReport,
    aiSuggestPending,
    aiSuggestion,
    handleAiProgressSync,
    handleAiSuggestNextTask,
  } = useAiProgressAssist({
    user,
    parsedCycleId,
    atlasRuntime,
    allScopeRefs,
    taskRefs,
    loadSnapshotForUser,
    onTaskSuggested: (taskRef) => {
      setFocusTaskRef(taskRef);
      setSelectedRef(taskRef);
    },
  });
  const [inspectorModalOpen, setInspectorModalOpen] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createModalParentRef, setCreateModalParentRef] = useState("");
  const createModalContext = useMemo(() => {
    if (!createModalParentRef || !atlasRuntime) {
      return { goalId: null, objectiveId: null, keyResultId: null };
    }
    const parentMeta = atlasRuntime.index[createModalParentRef];
    if (!parentMeta) {
      return { goalId: null, objectiveId: null, keyResultId: null };
    }
    const type = parentMeta.type;
    return {
      goalId: type === "GOAL" ? parentMeta.id : null,
      objectiveId: type === "OBJECTIVE" ? parentMeta.id : null,
      keyResultId: type === "KEY_RESULT" ? parentMeta.id : null,
    };
  }, [createModalParentRef, atlasRuntime]);
  const {
    alignmentContext,
    alignmentPending,
    alignmentError,
    alignmentTargetObjectiveId,
    alignmentDirection,
    setAlignmentTargetObjectiveId,
    setAlignmentDirection,
    inspectTaskWorkLogsPending,
    inspectTaskWorkLogsError,
    inspectTaskWorkLogPendingId,
    inspectTaskWorkLogsActionError,
    inspectTaskWorkLogsActionMessage,
    inspectTaskWorkHistoryRows,
    handleInspectorDeleteWorkLog,
    handleAlignmentCreate,
    handleAlignmentDelete,
  } = useInspectorAuxData({
    user,
    selectedMeta,
    parsedCycleId,
    loadSnapshotForUser,
  });
  const {
    inspectPending,
    inspectError,
    inspectMessage,
    inspectAnalysisPending,
    inspectAnalysisError,
    inspectAnalysis,
    inspectDraft,
    setInspectDraft,
    createPending,
    createError,
    createMessage,
    canCreateForContext,
    createDraft,
    setCreateDraft,
    deletePending,
    deleteError,
    deleteMessage,
    handleInspectorRunAnalysis,
    handleInspectorSave,
    handleNodeCreate,
    handleNodeDelete,
  } = useInspectorNodeActions({
    user,
    selectedMeta,
    parsedCycleId,
    createContext,
    focusTaskRef,
    loadSnapshotForUser,
    setSelectedRef,
    setFocusTaskRef,
  });
  useSelectionFocusSync({
    atlasRuntime,
    selectedRef,
    setSelectedRef,
    taskRefs,
    focusTaskRef,
    setFocusTaskRef,
    selectedMeta,
    cycleId,
    setCreateDraft,
  });

  const focusTaskMeta = useMemo(() => {
    if (!atlasRuntime || !focusTaskRef) {
      return null;
    }
    const meta = atlasRuntime.index[focusTaskRef];
    if (!meta || meta.type !== "TASK") {
      return null;
    }
    return meta;
  }, [atlasRuntime, focusTaskRef]);
  const focusTaskStartedAt = useMemo(() => {
    if (!focusTaskMeta || focusTaskMeta.type !== "TASK") {
      return "";
    }
    const task = focusTaskMeta.node as AtlasTaskSnapshot;
    return String(task.timer_started_at || "").trim();
  }, [focusTaskMeta]);
  const {
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
  } = useTimerSession({
    user,
    focusTaskId: focusTaskMeta?.id ?? null,
    focusTaskStartedAt,
    parsedCycleId,
    mode,
    loadSnapshotForUser,
    refreshDashboardModeData,
  });

  const mindmapTree = useMemo(() => {
    if (!mindmapPayload) {
      return null;
    }
    return buildMindmapTree((mindmapPayload as Record<string, unknown>).node, (mindmapPayload as Record<string, unknown>).node_type);
  }, [mindmapPayload]);

  const selectedInspectorTitle = useMemo(() => {
    if (!selectedMeta) {
      return "";
    }
    const baseTitle = String(selectedMeta.title || "").trim();
    if (baseTitle && !isGenericIndexedTitle(baseTitle, selectedMeta.type, selectedMeta.id)) {
      return baseTitle;
    }
    const nodePayloadTitle = String((selectedMeta.node as { title?: unknown }).title || "").trim();
    if (
      nodePayloadTitle &&
      !isGenericIndexedTitle(nodePayloadTitle, selectedMeta.type, selectedMeta.id)
    ) {
      return nodePayloadTitle;
    }
    const mindmapTitle = findMindmapNodeTitle(mindmapTree, selectedMeta.type, selectedMeta.id);
    if (mindmapTitle && !isGenericIndexedTitle(mindmapTitle, selectedMeta.type, selectedMeta.id)) {
      return mindmapTitle;
    }
    return baseTitle || `${nodeTypeLabel(selectedMeta.type)} ${selectedMeta.id}`;
  }, [mindmapTree, selectedMeta]);

  const { handleSignOut } = useShellAccessControl({
    authHydrated,
    user,
    isAdmin,
    mode,
    adminTab,
    adminAiHealth,
    adminPdfHealth,
    adminAuditSummary,
    routerReplace: (href) => router.replace(href),
    handleSidebarModeSelect,
    loadAdminResources,
    loadAdminHealth,
    loadAdminAuditSummary,
    setUser,
    clearSnapshot,
  });

  function renderMindmapTreeNode(node: MindmapTreeNode, depth = 0) {
    const nodeRef =
      node.id && (node.type === "GOAL" || node.type === "OBJECTIVE" || node.type === "KEY_RESULT" || node.type === "TASK")
        ? `${node.type === "KEY_RESULT" ? "key_result" : node.type.toLowerCase()}_${node.id}`
        : "";
    return (
      <div key={`${node.type}-${node.id || node.title}-${depth}`} style={{ marginTop: depth === 0 ? 0 : "0.28rem" }}>
        <button
          type="button"
          className={`atlas-node-item${nodeRef && selectedRef === nodeRef ? " is-active" : ""}`}
          style={{ width: "100%", paddingLeft: `${0.65 + depth * 0.85}rem` }}
          onClick={() => {
            if (!nodeRef) {
              return;
            }
            setSelectedRef(nodeRef);
            if (node.type === "TASK") {
              setFocusTaskRef(nodeRef);
            }
          }}
          disabled={!nodeRef}
        >
          <span className="atlas-node-tag">{node.type === "KEY_RESULT" ? "KR" : node.type === "NODE" ? "N" : node.type.charAt(0)}</span>
          <span className="atlas-node-title">{node.title}</span>
          <span className="atlas-node-progress">{node.progress !== null ? `${Math.round(node.progress)}%` : "-"}</span>
        </button>
        {node.children.map((child) => renderMindmapTreeNode(child, depth + 1))}
      </div>
    );
  }

  if (!authHydrated) {
    return (
      <main className="page-shell">
        <section className="panel" style={{ padding: "1rem" }}>
          <p className="kicker">Atlas SPA</p>
          <p style={{ margin: "0.2rem 0 0", color: "var(--ink-soft)" }}>Loading session...</p>
        </section>
      </main>
    );
  }

  if (!user) {
    return (
      <main className="page-shell">
        <section className="panel" style={{ padding: "1rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.62rem" }}>
            <img
              src="/okr-logo.webp"
              alt="OKR logo"
              width={30}
              height={54}
              style={{ display: "block", width: "30px", height: "54px", objectFit: "contain" }}
            />
            <h2 style={{ margin: 0, fontSize: "1.5rem" }}>OKR</h2>
          </div>
          <p style={{ margin: 0, color: "var(--ink-soft)" }}>
            Redirecting to login.{" "}
            <a href="/login" style={{ textDecoration: "underline" }}>
              Open login page
            </a>
            .
          </p>
        </section>
      </main>
    );
  }

  return (
    <main className="page-shell">
      <div className="spa-shell-layout">
        <aside className="panel spa-shell-sidebar">
          <div
            style={{
              marginTop: "0.1rem",
              border: "1px solid var(--line)",
              borderRadius: 10,
              padding: "0.55rem 0.58rem",
              background: "var(--surface-alt)",
            }}
          >
            <p className="kicker" style={{ margin: 0 }}>
              Task Timer
            </p>
            <label
              htmlFor="focus-task-ref"
              style={{ fontSize: "0.78rem", color: "var(--ink-soft)", display: "block", marginTop: "0.3rem" }}
            >
              Active Task
            </label>
            <select
              id="focus-task-ref"
              className="input"
              value={focusTaskRef}
              onChange={(event) => setFocusTaskRef(normalizeFocusTaskRef(event.target.value))}
              style={{ marginTop: "0.2rem" }}
            >
              <option value="">None</option>
              {taskRefs.map((taskRef) => {
                const taskMeta = atlasRuntime?.index[taskRef];
                if (!taskMeta) {
                  return null;
                }
                return (
                  <option key={taskRef} value={taskRef}>
                    {taskMeta.title} ({taskRef})
                  </option>
                );
              })}
            </select>

            <p style={{ margin: "0.28rem 0 0.2rem", fontSize: "0.82rem", color: "var(--ink-soft)" }}>
              Target: {focusTaskMeta ? `${focusTaskMeta.title} (#${focusTaskMeta.id})` : "No task selected"}
            </p>
            {focusTaskMeta ? (
              <p style={{ margin: "0 0 0.3rem", fontSize: "0.8rem", color: "var(--ink-soft)" }}>
                Timer status: {focusTaskRunning ? "Running" : "Stopped"}
              </p>
            ) : null}

            {focusTaskRunning ? (
              <button
                className="primary-button"
                type="button"
                onClick={() => setTimerModalOpen(true)}
                disabled={!user || !focusTaskMeta}
                style={{ width: "100%" }}
              >
                Open timer modal
              </button>
            ) : (
              <button
                className="primary-button"
                type="button"
                onClick={handleTimerStart}
                disabled={timerPending || !user || !focusTaskMeta}
                style={{ width: "100%" }}
              >
                {timerPending ? "Working..." : "Start timer"}
              </button>
            )}

            {timerError ? (
              <p style={{ margin: "0.36rem 0 0", color: "var(--error)", fontSize: "0.82rem" }}>{timerError}</p>
            ) : null}
            {timerMessage ? (
              <p style={{ margin: "0.36rem 0 0", color: "var(--accent)", fontSize: "0.82rem" }}>{timerMessage}</p>
            ) : null}

            <button
              className="primary-button"
              type="button"
              onClick={() => void handleAiSuggestNextTask()}
              disabled={aiSuggestPending || !user || taskRefs.length === 0}
              style={{ width: "100%", marginTop: "0.36rem" }}
            >
              {aiSuggestPending ? "Suggesting..." : "Suggest Next Task"}
            </button>
            {aiSuggestion ? (
              <p style={{ margin: "0.34rem 0 0", fontSize: "0.8rem", color: "var(--ink-soft)" }}>
                Suggested: {aiSuggestion.taskRef}
                {aiSuggestion.confidence !== null ? ` (${aiSuggestion.confidence}%)` : ""}
                {aiSuggestion.reason ? ` — ${aiSuggestion.reason}` : ""}
              </p>
            ) : null}
          </div>
          <h2 style={{ margin: "0.65rem 0 0.65rem", fontSize: "1.05rem" }}>Workspace</h2>
          <div className="spa-sidebar-links">
            {sidebarItems.map((item) => {
              const isActive = mode === item.mode;
              return (
                <button
                  key={item.id}
                  type="button"
                  className="spa-sidebar-link"
                  aria-current={isActive ? "page" : undefined}
                  onClick={() => handleSidebarModeSelect(item.mode)}
                >
                  <span>{item.label}</span>
                </button>
              );
            })}
          </div>
          <div
            style={{
              marginTop: "0.8rem",
              border: "1px solid var(--line)",
              borderRadius: 10,
              padding: "0.55rem 0.58rem",
              background: "var(--surface-alt)",
            }}
          >
            <div style={{ fontSize: "0.82rem", color: "var(--ink-soft)" }}>Signed in as</div>
            <strong style={{ display: "block", marginTop: "0.2rem" }}>{user.display_name}</strong>
            <button
              className="primary-button"
              type="button"
              onClick={handleSignOut}
              style={{ marginTop: "0.55rem", width: "100%" }}
            >
              Sign out
            </button>
          </div>
        </aside>
        <div>

      {mode === "atlas" ? (
      <>
      <AtlasModeControlsPanel
        cycleLabel={cycleDisplayLabel(resolvedCycle)}
        snapshotPending={snapshotPending}
        snapshotPollIntervalMs={snapshotPollIntervalMs}
        cycleId={effectiveCycleId}
        cycleOptions={cycleOptions}
        canManageCycleSelection={canManageCycleSelection}
        onCycleIdChange={setCycleId}
        ownerIdsInput={ownerIdsInput}
        onOwnerIdsInputChange={setOwnerIdsInput}
        canManageOwnerFilter={isAdmin}
        ownerFilterOptions={ownerFilterOptions}
        selectedOwnerIds={selectedOwnerIds}
        lens={lens}
        onLensChange={setLens}
        parsedOwnerIdsError={parsedOwnerIds.error}
        cycleResolveError={cycleResolveError}
        snapshotError={snapshotError}
      />
      <section className="panel atlas-parity-panel" style={{ marginTop: "0.9rem", padding: "0.9rem" }}>
        <AtlasFocusMapPanel
          filteredRefs={filteredRefs}
          atlasIndex={atlasRuntime?.index || null}
          selectedRef={selectedRef}
          onSelectRef={(ref) => {
            setSelectedRef(ref);
            setInspectorModalOpen(true);
          }}
          onAddChild={(parentRef) => {
            const parentMeta = atlasRuntime?.index[parentRef];
            if (parentMeta) {
              setCreateDraft((prev) => ({
                ...prev,
                createType:
                  parentMeta.type === "GOAL"
                    ? "objective"
                    : parentMeta.type === "OBJECTIVE"
                      ? "key_result"
                      : "task",
              }));
            }
            setCreateModalParentRef(parentRef);
            setCreateModalOpen(true);
          }}
          nodeQuery={nodeQuery}
          onNodeQueryChange={setNodeQuery}
          hasSnapshotPayload={Boolean(snapshotPayload)}
          nodeTagForType={(type) => TYPE_TAG[type as keyof typeof TYPE_TAG] || "N"}
        />

        <InspectorAiAssistPanel
          aiSyncPending={aiSyncPending}
          hasUser={Boolean(user)}
          hasAtlasRuntime={Boolean(atlasRuntime)}
          aiSyncReport={aiSyncReport}
          aiSyncError={aiSyncError}
          aiSyncMessage={aiSyncMessage}
          onRunAiSync={() => {
            void handleAiProgressSync(false);
          }}
        />
      </section>

      </>
      ) : mode === "admin" ? (
      <AdminModePanel
        isAdmin={isAdmin}
        adminTab={adminTab}
        setAdminTab={setAdminTab}
        adminCreateCycleDraft={adminCreateCycleDraft}
        setAdminCreateCycleDraft={setAdminCreateCycleDraft}
        onAdminCreateCycle={handleAdminCreateCycle}
        adminUserDraft={adminUserDraft}
        setAdminUserDraft={setAdminUserDraft}
        onAdminCreateUser={handleAdminCreateUser}
        adminTeamDraft={adminTeamDraft}
        setAdminTeamDraft={setAdminTeamDraft}
        onAdminCreateTeam={handleAdminCreateTeam}
        adminResetDraft={adminResetDraft}
        setAdminResetDraft={setAdminResetDraft}
        onAdminResetPassword={handleAdminResetPassword}
        adminBackupPending={adminBackupPending}
        onAdminBackupExport={handleAdminBackupExport}
        setAdminBackupFile={setAdminBackupFile}
        setAdminBackupRestoreResult={setAdminBackupRestoreResult}
        adminBackupConfirm={adminBackupConfirm}
        setAdminBackupConfirm={setAdminBackupConfirm}
        onAdminBackupRestore={handleAdminBackupRestore}
        adminBackupRestoreResult={adminBackupRestoreResult}
        formatOptionalDate={formatOptionalDate}
        adminHealthPending={adminHealthPending}
        onLoadAdminHealthConfig={() => {
          if (!user) {
            return;
          }
          void loadAdminHealth(user, false);
        }}
        onLoadAdminHealthLive={() => {
          if (!user) {
            return;
          }
          void loadAdminHealth(user, true);
        }}
        adminAuditSummary={adminAuditSummary}
        adminAuditSummaryPending={adminAuditSummaryPending}
        adminAuditSummaryError={adminAuditSummaryError}
        onLoadAdminAuditSummary={() => {
          if (!user) {
            return;
          }
          void loadAdminAuditSummary(user);
        }}
        adminAiHealth={adminAiHealth}
        adminPdfHealth={adminPdfHealth}
        adminCyclesPending={adminCyclesPending}
        adminDataPending={adminDataPending}
        adminCycleError={adminCycleError}
        adminDataError={adminDataError}
        adminCycleMessage={adminCycleMessage}
        adminCycles={adminCycles}
        onAdminSetCycleActive={handleAdminSetCycleActive}
        onAdminUpdateCycleOwner={handleAdminUpdateCycleOwner}
        onAdminDeleteCycle={handleAdminDeleteCycle}
        cyclePeriodLabel={cyclePeriodLabel}
        toDateInputValue={toDateInputValue}
        adminUsers={adminUsers}
        onAdminToggleUserActive={handleAdminToggleUserActive}
        adminTeams={adminTeams}
        setAdminTeams={setAdminTeams}
        onAdminUpdateTeam={handleAdminUpdateTeam}
        onAdminDeleteTeam={handleAdminDeleteTeam}
      />
      ) : (
      <section className="panel" style={{ marginTop: "0.9rem", padding: "0.9rem" }}>
        <p className="kicker">{modeDisplayLabel(mode)}</p>
        <h2 style={{ margin: "0.1rem 0 0.45rem", fontSize: "1.05rem" }}>
          {mode === "dashboard" ? "Dashboard Workspace" : "Workspace View"}
        </h2>
        {modeDataPending ? <p style={{ margin: "0.2rem 0 0", color: "var(--ink-soft)" }}>Loading...</p> : null}
        {modeDataError ? <p style={{ margin: "0.2rem 0 0", color: "var(--error)" }}>{modeDataError}</p> : null}
        {modeActionError ? <p style={{ margin: "0.2rem 0 0", color: "var(--error)" }}>{modeActionError}</p> : null}
        {modeActionMessage ? <p style={{ margin: "0.2rem 0 0", color: "var(--accent)" }}>{modeActionMessage}</p> : null}

        {mode === "dashboard" ? (
          <>
            <div className="report-card-grid" style={{ marginTop: "0.45rem" }}>
              <article className="report-metric-card">
                <p className="kicker" style={{ margin: 0 }}>Cycle</p>
                <strong>{cycleDisplayLabel(resolvedCycle)}</strong>
                <span>Current planning and delivery window</span>
              </article>
              <article className="report-metric-card">
                <p className="kicker" style={{ margin: 0 }}>Execution Completion</p>
                <strong>{dashboardCompletionPct}%</strong>
                <div className="report-progress-track" aria-hidden="true">
                  <span className="report-progress-fill" style={{ width: `${dashboardCompletionPct}%` }} />
                </div>
                <span>
                  {timelineStatusCounts.done}/{timelineRows.length || 0} cycle tasks done
                </span>
              </article>
              <article className="report-metric-card">
                <p className="kicker" style={{ margin: 0 }}>Risk Pressure</p>
                <strong>{dashboardRiskPressurePct}%</strong>
                <div className="report-progress-track" aria-hidden="true">
                  <span className="report-progress-fill risk" style={{ width: `${dashboardRiskPressurePct}%` }} />
                </div>
                <span>
                  {Math.round(Number(leadershipMetrics?.at_risk_count || 0))} at-risk KRs
                </span>
              </article>
              <article className="report-metric-card">
                <p className="kicker" style={{ margin: 0 }}>Focus Velocity (30d)</p>
                <strong>{dashboardFocusMinutes30d} min</strong>
                <span>{dashboardAvgDailyFocus30d} min/day average</span>
              </article>
              {rollup ? (
                <article className="report-metric-card">
                  <p className="kicker" style={{ margin: 0 }}>Program Structure</p>
                  <strong>
                    {rollup.goals}G / {rollup.objectives}O / {rollup.keyResults}KR
                  </strong>
                  <span>{rollup.tasks} tasks in hierarchy</span>
                </article>
              ) : null}
              <article className="report-metric-card">
                <p className="kicker" style={{ margin: 0 }}>Task Throughput</p>
                <strong>{timelineTasks.length}</strong>
                <span>{timelineLogs.length} work sessions in last 30 days</span>
              </article>
            </div>

            <div className="report-three-col" style={{ marginTop: "0.55rem" }}>
              <section className="report-panel">
                <div className="report-panel-head">
                  <h3>Trend Deltas (Last 15d vs Prior 15d)</h3>
                </div>
                <div className="report-list">
                  <article className="report-list-row compact">
                    <strong>Focus Minutes</strong>
                    <span>
                      {dashboardTrendDeltas.recentMinutes} vs {dashboardTrendDeltas.previousMinutes} min
                    </span>
                    <span
                      className={`delta-pill ${
                        dashboardTrendDeltas.minuteDelta > 0
                          ? "positive"
                          : dashboardTrendDeltas.minuteDelta < 0
                            ? "negative"
                            : "neutral"
                      }`}
                    >
                      {formatSignedDelta(dashboardTrendDeltas.minuteDelta)} min
                      {dashboardTrendDeltas.minuteDeltaPct !== null
                        ? ` (${formatSignedDelta(dashboardTrendDeltas.minuteDeltaPct)}%)`
                        : ""}
                    </span>
                  </article>
                  <article className="report-list-row compact">
                    <strong>Work Sessions</strong>
                    <span>
                      {dashboardTrendDeltas.recentSessions} vs {dashboardTrendDeltas.previousSessions} sessions
                    </span>
                    <span
                      className={`delta-pill ${
                        dashboardTrendDeltas.sessionDelta > 0
                          ? "positive"
                          : dashboardTrendDeltas.sessionDelta < 0
                            ? "negative"
                            : "neutral"
                      }`}
                    >
                      {formatSignedDelta(dashboardTrendDeltas.sessionDelta)} sessions
                    </span>
                  </article>
                  <article className="report-list-row compact">
                    <strong>Done Tasks</strong>
                    <span>
                      {dashboardTrendDeltas.recentDone} vs {dashboardTrendDeltas.previousDone} tasks
                    </span>
                    <span
                      className={`delta-pill ${
                        dashboardTrendDeltas.doneDelta > 0
                          ? "positive"
                          : dashboardTrendDeltas.doneDelta < 0
                            ? "negative"
                            : "neutral"
                      }`}
                    >
                      {formatSignedDelta(dashboardTrendDeltas.doneDelta)} tasks
                    </span>
                  </article>
                </div>
                <div className="report-status-grid" style={{ marginTop: "0.45rem" }}>
                  <div className="status-chip done">Done: {timelineStatusCounts.done}</div>
                  <div className="status-chip in-progress">In Progress: {timelineStatusCounts.inProgress}</div>
                  <div className="status-chip todo">Todo: {timelineStatusCounts.todo}</div>
                  <div className="status-chip blocked">Blocked: {timelineStatusCounts.blocked}</div>
                  <div className="status-chip overdue">Overdue: {timelineStatusCounts.overdue}</div>
                </div>
              </section>

              <section className="report-panel">
                <div className="report-panel-head">
                  <h3>Owner Load</h3>
                </div>
                <div className="report-list">
                  {dashboardOwnerLoad.length ? (
                    dashboardOwnerLoad.map((row) => (
                      <article key={row.owner} className="report-list-row compact">
                        <strong>{row.owner}</strong>
                        <span>
                          Active {row.active} • Done {row.completed} • Total {row.total}
                        </span>
                        <span>Blocked {row.blocked} • Overdue {row.overdue}</span>
                        <span className="muted">Pressure score: {row.pressureScore}</span>
                      </article>
                    ))
                  ) : (
                    <p className="report-empty">No owner load data available.</p>
                  )}
                </div>
              </section>

              <section className="report-panel">
                <div className="report-panel-head">
                  <h3>Top Focus Areas (30d)</h3>
                </div>
                <div className="report-list">
                  {dashboardTopTasks.map((row) => (
                    <article key={`${row.taskId || "none"}-${row.title}`} className="report-list-row compact">
                      <strong>{row.title}</strong>
                      <span>
                        {row.minutes} min in {row.sessions} sessions
                      </span>
                    </article>
                  ))}
                  {!timelineLogs.length ? (
                    <p className="report-empty">No focus logs captured in the last 30 days.</p>
                  ) : null}
                </div>
              </section>
            </div>

            <section className="report-panel" style={{ marginTop: "0.55rem" }}>
              <div className="report-panel-head">
                <h3>Risk Drill-Down</h3>
              </div>
              <div className="risk-grid">
                {dashboardRiskDrilldown.length ? (
                  dashboardRiskDrilldown.map((row) => (
                    <article key={row.key} className="risk-card">
                      <p className="kicker" style={{ margin: 0 }}>Key Result</p>
                      <strong>{row.title}</strong>
                      <p className="risk-detail">{row.reason}</p>
                      <div className="risk-meta">
                        <span>Owner: {row.owner}</span>
                        {row.deadline ? <span>Deadline: {row.deadline}</span> : null}
                        {row.confidence !== null ? <span>Confidence: {Math.round(row.confidence)}/10</span> : null}
                        {row.riskScore !== null ? <span>Risk score: {Math.round(row.riskScore)}</span> : null}
                        {row.lagDays !== null ? <span>Check-in lag: {Math.round(row.lagDays)}d</span> : null}
                      </div>
                    </article>
                  ))
                ) : (
                  <p className="report-empty">No KR-level risk signals found in the latest snapshot.</p>
                )}
              </div>
              {dashboardAtRiskRows.length && !dashboardRiskDrilldown.length ? (
                <div className="report-list" style={{ marginTop: "0.45rem" }}>
                  {dashboardAtRiskRows.map((row) => (
                    <article key={`${row.title}-${row.owner}`} className="report-list-row">
                      <strong>{row.title}</strong>
                      <span>{row.reason}</span>
                      <span className="muted">Owner: {row.owner}</span>
                    </article>
                  ))}
                </div>
              ) : null}
            </section>

            <DashboardLeadershipPanel
              canViewLeadership={isAdmin || String(user.role || "").toLowerCase() === "manager"}
              leadershipPending={leadershipPending}
              teamCoachPending={teamCoachPending}
              strategyPulsePending={strategyPulsePending}
              parsedCycleId={parsedCycleId}
              leadershipError={leadershipError}
              teamCoachError={teamCoachError}
              strategyPulseError={strategyPulseError}
              leadershipMetrics={leadershipMetrics}
              teamCoachSummary={teamCoachSummary}
              strategyPulseSummary={strategyPulseSummary}
              onRefreshMetrics={() => {
                void loadLeadershipMetricsSnapshot(user);
              }}
              onGenerateTeamCoach={() => {
                void handleGenerateTeamCoachSummary();
              }}
              onGenerateStrategyPulse={() => {
                void handleGenerateStrategyPulseSummary();
              }}
            />
          </>
        ) : null}

        {mode === "weekly" ? (
          <WeeklyModePanel
            weekRangeLabel={`${startOfWeekIso()} to ${endOfWeekIso()}`}
            cycleLabel={cycleDisplayLabel(resolvedCycle)}
            reportExportPending={reportExportPending}
            reportAiPending={reportAiPending}
            reportExportError={reportExportError}
            reportAiError={reportAiError}
            onReportExport={(format) => {
              void handleReportExport(format);
            }}
            onGenerateAiSummary={() => {
              void handleReportAiSummaryGenerate();
            }}
            weeklyTotalMinutes={weeklyTotalMinutes}
            weeklySessionCount={weeklyLogs.length}
            weeklyAverageMinutes={weeklyAverageMinutes}
            weeklyPriorityCoverage={weeklyPriorityCoverage}
            weeklyKrsNeedingCheckInCount={weeklyKrsNeedingCheckIn.length}
            reportAiSummary={reportAiSummary}
            weeklyPlanData={weeklyPlanData}
            weeklyDraft={weeklyDraft}
            setWeeklyDraft={setWeeklyDraft}
            onSaveWeeklyPlan={() => {
              void handleWeeklyPlanSave();
            }}
            modeActionPending={modeActionPending}
            weeklyTopTasks={weeklyTopTasks}
            weeklyKrsNeedingCheckIn={weeklyKrsNeedingCheckIn}
            weeklyReviewExperiments={weeklyReviewExperiments}
          />
        ) : null}

        {mode === "daily" ? (
          <DailyModePanel
            todayLabel={new Date().toLocaleDateString()}
            cycleLabel={cycleDisplayLabel(resolvedCycle)}
            reportExportPending={reportExportPending}
            reportAiPending={reportAiPending}
            reportExportError={reportExportError}
            reportAiError={reportAiError}
            onReportExport={(format) => {
              void handleReportExport(format);
            }}
            onGenerateAiSummary={() => {
              void handleReportAiSummaryGenerate();
            }}
            dailyLogsFiltered={dailyLogsFiltered}
            dailyTotalMinutes={dailyTotalMinutes}
            dailyAverageMinutes={dailyAverageMinutes}
            dailyDeepWorkShare={dailyDeepWorkShare}
            reportAiSummary={reportAiSummary}
            dailyLogQuery={dailyLogQuery}
            onDailyLogQueryChange={setDailyLogQuery}
            dailyTimeBands={dailyTimeBands}
            dailyTopTasks={dailyTopTasks}
            formatOptionalDate={formatOptionalDate}
          />
        ) : null}

        {mode === "ritual" ? (
          <RitualModePanel
            ritualStep={ritualStep}
            setRitualStep={setRitualStep}
            cycleLabel={cycleDisplayLabel(resolvedCycle)}
            ritualKrs={ritualKrs}
            ritualSubmittedCount={ritualSubmittedCount}
            ritualReviewLogs={ritualReviewLogs}
            ritualReviewExperiments={ritualReviewExperiments}
            toDateShortLabel={toDateShortLabel}
            ritualReviewRange={ritualReviewRange}
            retroDraft={retroDraft}
            setRetroDraft={setRetroDraft}
            handleRetroCreate={handleRetroCreate}
            startOfWeekIso={startOfWeekIso}
            modeActionPending={modeActionPending}
            ritualCheckInDrafts={ritualCheckInDrafts}
            ritualExperimentsByKr={ritualExperimentsByKr}
            ritualExperimentDrafts={ritualExperimentDrafts}
            ritualExperimentFormOpen={ritualExperimentFormOpen}
            setRitualExperimentFormOpen={setRitualExperimentFormOpen}
            ritualExperimentPending={ritualExperimentPending}
            ritualExperimentError={ritualExperimentError}
            ritualExperimentMessage={ritualExperimentMessage}
            ritualExperimentCloseDrafts={ritualExperimentCloseDrafts}
            ritualExperimentActionPending={ritualExperimentActionPending}
            updateRitualExperimentCloseDraft={updateRitualExperimentCloseDraft}
            ritualExperimentActionError={ritualExperimentActionError}
            ritualExperimentActionMessage={ritualExperimentActionMessage}
            updateRitualCheckInDraft={updateRitualCheckInDraft}
            updateRitualExperimentDraft={updateRitualExperimentDraft}
            handleRitualExperimentCreate={handleRitualExperimentCreate}
            handleRitualExperimentStart={handleRitualExperimentStart}
            handleRitualExperimentClose={handleRitualExperimentClose}
            formatOptionalNumber={formatOptionalNumber}
            ritualCheckInPending={ritualCheckInPending}
            handleRitualCheckInSubmit={handleRitualCheckInSubmit}
            ritualCheckInError={ritualCheckInError}
            ritualCheckInMessage={ritualCheckInMessage}
            weeklyPlanData={weeklyPlanData}
            weeklyDraft={weeklyDraft}
            setWeeklyDraft={setWeeklyDraft}
            handleWeeklyPlanSave={handleWeeklyPlanSave}
            endOfWeekIso={endOfWeekIso}
          />
        ) : null}

        {mode === "retrobox" ? (
          <RetroboxModePanel
            retroDraft={retroDraft}
            onRetroDraftChange={(patch) => {
              setRetroDraft((prev) => ({ ...prev, ...patch }));
            }}
            modeActionPending={modeActionPending}
            onAddRetrospective={() => {
              void handleRetroCreate();
            }}
            retroItems={retroItems}
            formatOptionalDate={formatOptionalDate}
          />
        ) : null}

        {mode === "timeline" ? (
          <TimelineModePanel
            timelineRows={timelineRows}
            timelineRowsFiltered={timelineRowsFiltered}
            timelineStatusCounts={timelineStatusCounts}
            timelineQuery={timelineQuery}
            onTimelineQueryChange={setTimelineQuery}
            timelineStatusFilter={timelineStatusFilter}
            onTimelineStatusFilterChange={setTimelineStatusFilter}
            timelineWindow={timelineWindow}
            timelineLogs={timelineLogs}
            timelineStatusLabel={timelineStatusLabel}
            toDateShortLabel={toDateShortLabel}
            formatOptionalDate={formatOptionalDate}
            onOpenTaskInAtlas={handleOpenTaskInAtlas}
          />
        ) : null}
      </section>
      )}
        </div>
      </div>
      {inspectorModalOpen && selectedMeta && atlasRuntime ? (
        <div className="timer-modal-overlay" role="dialog" aria-modal="true" aria-label="Inspector">
          <div className="timer-modal panel" style={{ maxWidth: "28rem", maxHeight: "85vh", overflowY: "auto" }}>
            <div className="timer-modal-head">
              <div>
                <p className="kicker" style={{ margin: 0 }}>Inspector</p>
                <h3 style={{ margin: "0.12rem 0 0" }}>
                  {selectedInspectorTitle}
                </h3>
              </div>
              <button
                className="primary-button"
                type="button"
                onClick={() => setInspectorModalOpen(false)}
              >
                Close
              </button>
            </div>

            <p style={{ margin: "0.4rem 0 0", color: "var(--ink-soft)", fontSize: "0.82rem", minHeight: "2rem" }}>
              {selectedMeta.description || "No description."}
            </p>

            <div className="atlas-progress-wrap" style={{ marginTop: "0.5rem" }}>
              <div className="atlas-progress-track">
                <div
                  className="atlas-progress-fill"
                  style={{ width: `${Math.max(0, Math.min(100, selectedMeta.progress))}%` }}
                />
              </div>
              <span className="atlas-progress-label">Progress {selectedMeta.progress}%</span>
            </div>

            <p style={{ margin: "0.4rem 0 0", fontSize: "0.82rem", color: "var(--ink-soft)" }}>
              Owner: {selectedMeta.ownerName}
            </p>
            <p style={{ margin: "0.2rem 0 0", fontSize: "0.78rem", color: "var(--ink-soft)" }}>
              Path: {selectedMeta.path.map((ref) => atlasRuntime.index[ref]?.title || ref).join(" > ")}
            </p>

            <InspectorEditAnalysisPanel
              inspectDraft={inspectDraft}
              onInspectDraftChange={(patch) => {
                setInspectDraft((prev) => ({ ...prev, ...patch }));
              }}
              onInspectorSave={handleInspectorSave}
              inspectPending={inspectPending}
              hasUser={Boolean(user)}
              onNodeDelete={() => {
                void handleNodeDelete();
                setInspectorModalOpen(false);
              }}
              deletePending={deletePending}
              deleteError={deleteError}
              deleteMessage={deleteMessage}
              selectedTypeLabel={nodeTypeLabel(selectedMeta.type)}
              selectedNodeType={selectedMeta.type}
              inspectError={inspectError}
              inspectMessage={inspectMessage}
              inspectAnalysis={inspectAnalysis}
              onRunAnalysis={selectedMeta.type === "KEY_RESULT" ? () => {
                void handleInspectorRunAnalysis();
              } : undefined}
              inspectAnalysisPending={inspectAnalysisPending}
              inspectAnalysisError={inspectAnalysisError}
            />

            <dl className="atlas-kv-grid">
              {selectedNodeDetails(selectedMeta, { formatOptionalDate, formatOptionalNumber }).map(([label, value]) => (
                <div key={`${label}-${value}`}>
                  <dt>{label}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>

            {selectedMeta.type === "TASK" ? (
              <InspectorTaskWorkHistoryPanel
                inspectTaskWorkLogsPending={inspectTaskWorkLogsPending}
                inspectTaskWorkLogsError={inspectTaskWorkLogsError}
                inspectTaskWorkLogsActionError={inspectTaskWorkLogsActionError}
                inspectTaskWorkLogsActionMessage={inspectTaskWorkLogsActionMessage}
                inspectTaskWorkHistoryRows={inspectTaskWorkHistoryRows}
                inspectTaskWorkLogPendingId={inspectTaskWorkLogPendingId}
                hasUser={Boolean(user)}
                formatOptionalDate={formatOptionalDate}
                onDeleteWorkLog={(workLogId) => {
                  void handleInspectorDeleteWorkLog(workLogId);
                }}
              />
            ) : null}

            {selectedMeta.type === "OBJECTIVE" ? (
              <InspectorAlignmentPanel
                alignmentPending={alignmentPending}
                alignmentError={alignmentError}
                alignmentContext={alignmentContext}
                alignmentDirection={alignmentDirection}
                alignmentTargetObjectiveId={alignmentTargetObjectiveId}
                onAlignmentDirectionChange={setAlignmentDirection}
                onAlignmentTargetObjectiveIdChange={setAlignmentTargetObjectiveId}
                onAlignmentCreate={() => {
                  void handleAlignmentCreate();
                }}
                onAlignmentDelete={(edgeId) => {
                  void handleAlignmentDelete(edgeId);
                }}
              />
            ) : null}
          </div>
        </div>
      ) : null}

      {createModalOpen ? (
        <div className="timer-modal-overlay" role="dialog" aria-modal="true" aria-label="Create node">
          <div className="timer-modal panel" style={{ maxWidth: "28rem", maxHeight: "85vh", overflowY: "auto" }}>
            <div className="timer-modal-head">
              <div>
                <p className="kicker" style={{ margin: 0 }}>Manage Nodes</p>
                <h3 style={{ margin: "0.12rem 0 0" }}>
                  Create {createTypeLabel(createDraft.createType)}
                </h3>
              </div>
              <button
                className="primary-button"
                type="button"
                onClick={() => setCreateModalOpen(false)}
              >
                Close
              </button>
            </div>

            <InspectorManageNodesPanel
              createDraft={createDraft}
              onCreateDraftChange={(patch) => {
                setCreateDraft((prev) => ({ ...prev, ...patch }));
              }}
              createContext={createModalContext}
              canCreateForContext={Boolean(
                createDraft.createType === "goal" ||
                (createDraft.createType === "objective" && createModalContext.goalId) ||
                (createDraft.createType === "key_result" && createModalContext.objectiveId) ||
                (createDraft.createType === "task" && createModalContext.keyResultId),
              )}
              createTypeLabel={createTypeLabel}
              cycleLabel={cycleDisplayLabel(resolvedCycle)}
              onCreateNode={() => {
                void handleNodeCreate().then(() => {
                  setCreateModalOpen(false);
                });
              }}
              createPending={createPending}
              hasUser={Boolean(user)}
              createError={createError}
              createMessage={createMessage}
              deleteError={deleteError}
              deleteMessage={deleteMessage}
            />
          </div>
        </div>
      ) : null}

      {timerModalOpen && focusTaskRunning ? (
        <div className="timer-modal-overlay" role="dialog" aria-modal="true" aria-label="Focus timer session">
          <div className="timer-modal panel">
            <div className="timer-modal-head">
              <div>
                <p className="kicker" style={{ margin: 0 }}>Focus Timer</p>
                <h3 style={{ margin: "0.12rem 0 0" }}>
                  {focusTaskMeta ? focusTaskMeta.title : "Active task"}
                </h3>
              </div>
              <button
                className="primary-button"
                type="button"
                onClick={() => setTimerModalOpen(false)}
              >
                Hide
              </button>
            </div>

            <p style={{ margin: "0.3rem 0 0", color: "var(--ink-soft)", fontSize: "0.82rem" }}>
              Started: {activeTimerStartedAt ? formatOptionalDate(activeTimerStartedAt) : "-"}
            </p>
            <div className="timer-elapsed">{formatElapsedClock(activeTimerElapsedSeconds)}</div>

            <label
              htmlFor="timer-summary-modal"
              style={{ display: "block", marginTop: "0.25rem", fontSize: "0.82rem", color: "var(--ink-soft)" }}
            >
              Session summary
            </label>
            <textarea
              id="timer-summary-modal"
              className="input"
              value={timerSummary}
              onChange={(event) => setTimerSummary(event.target.value)}
              placeholder="Write what was completed, blockers, and next action."
              rows={4}
              style={{ marginTop: "0.2rem" }}
            />

            <div className="timer-modal-actions">
              <button
                className="primary-button"
                type="button"
                onClick={handleTimerStop}
                disabled={timerPending || !user}
              >
                {timerPending ? "Saving..." : "Stop timer + save log"}
              </button>
              <button
                className="primary-button"
                type="button"
                onClick={() => setTimerModalOpen(false)}
              >
                Close
              </button>
            </div>

            {timerError ? (
              <p style={{ margin: "0.36rem 0 0", color: "var(--error)", fontSize: "0.82rem" }}>{timerError}</p>
            ) : null}
            {timerMessage ? (
              <p style={{ margin: "0.36rem 0 0", color: "var(--accent)", fontSize: "0.82rem" }}>{timerMessage}</p>
            ) : null}
          </div>
        </div>
      ) : null}
    </main>
  );
}
