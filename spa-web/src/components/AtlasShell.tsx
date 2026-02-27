"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import {
  atlasRollup,
  buildAtlasIndexFromSnapshot,
  flattenScopeRefs,
  nodeTypeLabel,
  type AtlasIndexNode,
  type AtlasKeyResultSnapshot,
  type AtlasObjectiveSnapshot,
  type AtlasSnapshotResponse,
  type AtlasTaskSnapshot,
} from "@/lib/atlas";
import {
  analyzeNodeAi,
  analyzeTeamCoachAi,
  readStrategyPulseAi,
  createCheckInMutation,
  closeExperimentMutation,
  createExperimentMutation,
  readAdminDbBackup,
  restoreAdminDbBackup,
  readAdminAiHealth,
  readAdminPdfHealth,
  createCycleMutation,
  createNodeMutation,
  createRetrospectiveMutation,
  createTeamMutation,
  createUserMutation,
  createWeeklyPlanMutation,
  deleteCycleMutation,
  deleteNodeMutation,
  deleteTeamMutation,
  readAtlasSnapshot,
  readBackendJob,
  readBackendQuery,
  readCyclesQuery,
  readLeadershipMetrics,
  readSessionUser,
  readSpaRolloutConfig,
  resetUserPasswordMutation,
  logoutSession,
  startTaskTimer,
  stopTaskTimer,
  submitBackendJob,
  updateCycleMutation,
  updateExperimentMutation,
  updateTeamMutation,
  updateNodeMutation,
  updateUserMutation,
  type AdminAiHealthResponse,
  type AdminDbRestoreResponse,
  type AdminPdfHealthResponse,
  type AsyncJobView,
  type AuthUser,
  type CycleSummary,
  type ExperimentMutationResponse,
  type ExperimentDecisionType,
  type LeadershipMetricsResponse,
  type NodeTypePath,
  type TeamMutationResponse,
  type UserMutationResponse,
} from "@/lib/api";
import {
  DEFAULT_LENS,
  DEFAULT_MODE,
  buildDeepLinkQuery,
  normalizeFocusTaskRef,
  parseDeepLink,
} from "@/lib/deeplink";
import {
  SIDEBAR_ITEMS,
  modeDisplayLabel,
  modeForPath,
  pathForMode,
} from "@/components/atlas-shell/navigation";
import {
  createTypeLabel,
  mutationNodeRef,
  nearestAncestorId,
  nodeTypeToPath,
} from "@/components/atlas-shell/nodeMutation";
import { selectedNodeDetails } from "@/components/atlas-shell/inspectorDetails";
import AdminModePanel, {
  type AdminCreateCycleDraft,
  type AdminResetDraft,
  type AdminTab,
  type AdminTeamDraft,
  type AdminUserDraft,
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
import {
  evaluateSpaRollout,
  rolloutReasonMessage,
  type RolloutDecision,
  type SpaRolloutConfig,
} from "@/lib/rollout";

type InspectorEditDraft = {
  title: string;
  description: string;
  progress: string;
};

type NodeCreateDraft = {
  createType: NodeTypePath;
  title: string;
  description: string;
  cycleId: string;
  tags: string;
  targetValue: string;
  unit: string;
  estimatedMinutes: string;
  assigneeId: string;
};

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
type KeyResultRead = {
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
type ExperimentRead = {
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
  decision?: "ADOPT" | "ITERATE" | "ABANDON" | null;
  decision_rationale?: string | null;
  expected_effect_direction?: "UP" | "DOWN" | null;
  expected_effect_size?: number | null;
};
type ExperimentCloseDraft = {
  decision: ExperimentDecisionType;
  rationale: string;
};
type RetroRead = {
  id: number;
  week_start_date?: string | null;
  content?: string | null;
  sentiment?: string | null;
  created_at?: string | null;
};
type AdminUserRead = UserMutationResponse;
type AdminTeamRead = TeamMutationResponse;
type AiProgressUndoItem = {
  krId: number;
  title: string;
  previousProgress: number;
  newProgress: number;
};

type AiSyncReport = {
  total: number;
  analyzed: number;
  applied: number;
  planned: number;
  missingAiScore: number;
  skippedDeltaCap: number;
  skippedDecrease: number;
  unchanged: number;
  failed: string[];
};

type AiTaskSuggestion = {
  taskRef: string;
  reason: string;
  confidence: number | null;
};

type CheckInDraft = {
  value: string;
  confidence: string;
  comment: string;
  variationType: "COMMON_CAUSE" | "SPECIAL_CAUSE";
  specialCauseNote: string;
  experimentId: string;
};

type ExperimentDraft = {
  hypothesis: string;
  changeDescription: string;
  expectedEffectDirection: "" | "UP" | "DOWN";
  expectedEffectSize: string;
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

type AnalysisSummary = {
  efficiencyScore: number | null;
  effectivenessScore: number | null;
  overallScore: number | null;
  summary: string;
  gapAnalysis: string;
  qualityAssessment: string;
  deadlineWarnings: string[];
  proposedTasks: string[];
  raw: Record<string, unknown> | null;
};

type ReportAiSummary = {
  summaryMarkdown: string;
  highlights: string[];
  focusAnalysis: string;
};

type TeamCoachSummary = {
  healthScore: number | null;
  healthGrade: string;
  topPriorities: string[];
  quickWins: string[];
  watchOuts: string[];
  dimensionNotes: string[];
};

type StrategyPulseSummary = {
  burnoutRisk: string;
  burnoutScore: number | null;
  avgDailyMinutes: number | null;
  completedTasks14d: number | null;
  gapSignals: string[];
  predictiveOutlook: string;
  confidenceLevel: number | null;
  mitigationSteps: string[];
  strategicPivots: string[];
  portfolioActions: string[];
};

type MindmapTreeNode = {
  id: number | null;
  type: "GOAL" | "OBJECTIVE" | "KEY_RESULT" | "TASK" | "NODE";
  title: string;
  progress: number | null;
  children: MindmapTreeNode[];
};

const TYPE_TAG: Record<AtlasIndexNode["type"], string> = {
  GOAL: "G",
  OBJECTIVE: "O",
  KEY_RESULT: "KR",
  TASK: "T",
};

const AI_SYNC_MAX_DELTA = 40;
const AI_SYNC_ALLOW_DECREASE = false;
const DASHBOARD_REFRESH_INTERVAL_MS = 30_000;

function parseOwnerIds(raw: string): { value: number[] | undefined; error: string } {
  const normalized = String(raw || "").trim();
  if (!normalized) {
    return { value: undefined, error: "" };
  }

  const parsed = normalized
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => Number.parseInt(item, 10));

  if (parsed.some((value) => !Number.isFinite(value) || value <= 0)) {
    return {
      value: undefined,
      error: "Owner IDs must be comma-separated positive integers.",
    };
  }

  return {
    value: Array.from(new Set(parsed)),
    error: "",
  };
}

function parsePreviewBypass(search: string): boolean {
  const params = new URLSearchParams(String(search || ""));
  const raw = String(params.get("spa_preview") || "").trim().toLowerCase();
  return raw === "1" || raw === "true" || raw === "yes" || raw === "on";
}

function formatOptionalNumber(value: unknown): string {
  if (typeof value === "number" && Number.isFinite(value)) {
    return `${value}`;
  }
  return "-";
}

function formatOptionalDate(value: unknown): string {
  if (!value) {
    return "-";
  }
  const parsed = parseDateOrNull(value);
  if (!parsed || Number.isNaN(parsed.getTime())) {
    return String(value);
  }
  return parsed.toLocaleString();
}

function toDateInputValue(value: unknown): string {
  const text = String(value || "").trim();
  if (!text) {
    return "";
  }
  const parsed = new Date(text);
  if (Number.isNaN(parsed.getTime())) {
    return "";
  }
  const month = `${parsed.getMonth() + 1}`.padStart(2, "0");
  const day = `${parsed.getDate()}`.padStart(2, "0");
  return `${parsed.getFullYear()}-${month}-${day}`;
}

function toIsoStart(dateValue: string): string {
  return `${dateValue}T00:00:00Z`;
}

function toIsoEnd(dateValue: string): string {
  return `${dateValue}T23:59:59Z`;
}

function quarterLabel(dateLike: unknown): string {
  const text = String(dateLike || "").trim();
  if (!text) {
    return "";
  }
  const parsed = new Date(text);
  if (Number.isNaN(parsed.getTime())) {
    return "";
  }
  const quarter = Math.floor(parsed.getMonth() / 3) + 1;
  return `Q${quarter}-${parsed.getFullYear()}`;
}

function cyclePeriodLabel(cycle: Pick<CycleSummary, "start_date" | "end_date"> | null): string {
  if (!cycle) {
    return "";
  }
  const start = quarterLabel(cycle.start_date);
  const end = quarterLabel(cycle.end_date);
  if (start && end && start !== end) {
    return `${start} to ${end}`;
  }
  return start || end;
}

function cycleDisplayLabel(cycle: ResolvedCycle | null): string {
  if (!cycle) {
    return "Resolving...";
  }
  const period = cyclePeriodLabel(cycle);
  if (period) {
    return period;
  }
  const title = String(cycle.title || "").trim();
  return title || `Cycle ${cycle.id}`;
}

function cycleOptionLabel(cycle: Pick<CycleSummary, "id" | "title" | "start_date" | "end_date" | "is_active">): string {
  const period = cyclePeriodLabel(cycle);
  const title = String(cycle.title || "").trim();
  const base = period || title || `Cycle ${cycle.id}`;
  return cycle.is_active ? `${base} (active)` : base;
}

function normalizeTaskStatus(raw: unknown): string {
  const text = String(raw || "").trim().toUpperCase();
  if (text === "IN ACTION") {
    return "IN_PROGRESS";
  }
  if (text === "IN PROGRESS") {
    return "IN_PROGRESS";
  }
  if (text === "TODO" || text === "IN_PROGRESS" || text === "DONE" || text === "BLOCKED") {
    return text;
  }
  return "TODO";
}

function timelineStatusLabel(status: string): string {
  if (status === "IN_PROGRESS") {
    return "In Progress";
  }
  if (status === "DONE") {
    return "Done";
  }
  if (status === "BLOCKED") {
    return "Blocked";
  }
  return "Todo";
}

function parseDateOrNull(raw: unknown): Date | null {
  const text = String(raw || "").trim();
  if (!text) {
    return null;
  }
  // Canonicalize backend datetime strings to strict ISO-8601 UTC with
  // millisecond precision. This prevents local-time interpretation drift.
  let normalized = text;
  const matched = normalized.match(
    /^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})(?:\.(\d+))?([zZ]|[+\-]\d{2}:\d{2})?$/,
  );
  if (matched) {
    const [, datePart, timePart, fractionalRaw, timezoneRaw] = matched;
    const fractional = fractionalRaw
      ? `.${fractionalRaw.slice(0, 3).padEnd(3, "0")}`
      : "";
    const timezone = timezoneRaw
      ? (timezoneRaw.toUpperCase() === "Z" ? "Z" : timezoneRaw)
      : "Z";
    normalized = `${datePart}T${timePart}${fractional}${timezone}`;
  }
  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }
  return parsed;
}

function addDays(date: Date, days: number): Date {
  const clone = new Date(date.getTime());
  clone.setDate(clone.getDate() + days);
  return clone;
}

function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate(), 0, 0, 0, 0);
}

function endOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate(), 23, 59, 59, 999);
}

function reviewWindow(): { start: Date; end: Date } {
  const end = endOfDay(new Date());
  const start = startOfDay(addDays(end, -7));
  return { start, end };
}

function toDateShortLabel(value: Date): string {
  return value.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

function formatElapsedClock(totalSeconds: number): string {
  const safe = Math.max(0, Math.floor(Number(totalSeconds) || 0));
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const seconds = safe % 60;
  return `${`${hours}`.padStart(2, "0")}:${`${minutes}`.padStart(2, "0")}:${`${seconds}`.padStart(2, "0")}`;
}

function clampProgress(value: unknown): number {
  const raw = Number(value);
  if (!Number.isFinite(raw)) {
    return 0;
  }
  const rounded = Math.round(raw);
  if (rounded < 0) {
    return 0;
  }
  if (rounded > 100) {
    return 100;
  }
  return rounded;
}

function sumLogMinutes(logs: WorkLogRead[]): number {
  return Math.round(
    logs.reduce((sum, item) => sum + Number(item.duration_minutes || 0), 0),
  );
}

function averageLogMinutes(logs: WorkLogRead[]): number {
  if (!logs.length) {
    return 0;
  }
  return Math.round(sumLogMinutes(logs) / logs.length);
}

function groupLogsByTask(logs: WorkLogRead[]): Array<{
  taskId: number | null;
  title: string;
  minutes: number;
  sessions: number;
}> {
  const aggregate = new Map<string, { taskId: number | null; title: string; minutes: number; sessions: number }>();
  for (const log of logs) {
    const rawTaskId = Number(log.task_id);
    const taskId = Number.isFinite(rawTaskId) && rawTaskId > 0 ? rawTaskId : null;
    const title = String(log.task?.title || (taskId ? `Task #${taskId}` : "Unknown task"));
    const key = `${taskId || "none"}:${title}`;
    const row = aggregate.get(key) || { taskId, title, minutes: 0, sessions: 0 };
    row.minutes += Number(log.duration_minutes || 0);
    row.sessions += 1;
    aggregate.set(key, row);
  }
  return [...aggregate.values()]
    .map((row) => ({ ...row, minutes: Math.round(row.minutes) }))
    .sort((left, right) => right.minutes - left.minutes);
}

function formatSignedDelta(value: number): string {
  const rounded = Math.round(Number(value || 0));
  if (rounded > 0) {
    return `+${rounded}`;
  }
  return `${rounded}`;
}

function aiProgressDecision(
  currentProgress: unknown,
  aiScore: unknown,
  maxDelta: number,
  allowDecrease: boolean,
): {
  action: "apply" | "skip";
  reason: "within_policy" | "missing_ai_score" | "no_change" | "decrease_blocked" | "delta_cap";
  current: number;
  proposed: number | null;
  delta: number | null;
} {
  const current = clampProgress(currentProgress);
  const parsedAi = Number(aiScore);
  if (!Number.isFinite(parsedAi)) {
    return { action: "skip", reason: "missing_ai_score", current, proposed: null, delta: null };
  }
  const proposed = clampProgress(parsedAi);
  const delta = proposed - current;
  const boundedDelta = clampProgress(maxDelta);
  if (delta === 0) {
    return { action: "skip", reason: "no_change", current, proposed, delta };
  }
  if (delta < 0 && !allowDecrease) {
    return { action: "skip", reason: "decrease_blocked", current, proposed, delta };
  }
  if (Math.abs(delta) > boundedDelta) {
    return { action: "skip", reason: "delta_cap", current, proposed, delta };
  }
  return { action: "apply", reason: "within_policy", current, proposed, delta };
}

function parseNumberOrNull(value: unknown): number | null {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function parseAnalysisSummary(raw: unknown): AnalysisSummary {
  let payload: Record<string, unknown> | null = null;
  if (raw && typeof raw === "object") {
    payload = raw as Record<string, unknown>;
  } else if (typeof raw === "string" && raw.trim()) {
    try {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === "object") {
        payload = parsed as Record<string, unknown>;
      }
    } catch {
      payload = null;
    }
  }
  const warnings = Array.isArray(payload?.deadline_warnings)
    ? payload?.deadline_warnings.map((item) => String(item || "").trim()).filter(Boolean)
    : [];
  const proposed = Array.isArray(payload?.proposed_tasks)
    ? payload?.proposed_tasks
        .map((item) => {
          if (typeof item === "string") {
            return String(item || "").trim();
          }
          if (!item || typeof item !== "object") {
            return "";
          }
          const row = item as Record<string, unknown>;
          return String(row.title || row.task || row.name || "").trim();
        })
        .filter(Boolean)
    : [];
  return {
    efficiencyScore: parseNumberOrNull(payload?.efficiency_score),
    effectivenessScore: parseNumberOrNull(payload?.effectiveness_score),
    overallScore: parseNumberOrNull(payload?.overall_score),
    summary: String(payload?.summary || "").trim(),
    gapAnalysis: String(payload?.gap_analysis || "").trim(),
    qualityAssessment: String(payload?.quality_assessment || "").trim(),
    deadlineWarnings: warnings,
    proposedTasks: proposed,
    raw: payload,
  };
}

function parseReportAiSummary(raw: unknown): ReportAiSummary {
  const payload =
    raw && typeof raw === "object" ? (raw as Record<string, unknown>) : ({} as Record<string, unknown>);
  const highlights = Array.isArray(payload.highlights)
    ? payload.highlights.map((row) => String(row || "").trim()).filter(Boolean)
    : [];
  return {
    summaryMarkdown: String(payload.summary_markdown || "").trim(),
    highlights,
    focusAnalysis: String(payload.focus_analysis || "").trim(),
  };
}

function parseStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => String(item || "").trim()).filter(Boolean);
}

function parseTeamCoachSummary(raw: unknown): TeamCoachSummary {
  const payload =
    raw && typeof raw === "object" ? (raw as Record<string, unknown>) : ({} as Record<string, unknown>);
  return {
    healthScore: parseNumberOrNull(payload.health_score),
    healthGrade: String(payload.health_grade || "").trim(),
    topPriorities: parseStringArray(payload.top_priorities),
    quickWins: parseStringArray(payload.quick_wins),
    watchOuts: parseStringArray(payload.watch_outs),
    dimensionNotes: parseStringArray(payload.dimension_notes),
  };
}

function parseTeamCoachFromCoachingPayload(raw: unknown): TeamCoachSummary | null {
  const payload = asRecord(raw);
  const coaching = asRecord(payload?.coaching);
  if (!coaching) {
    return null;
  }
  const dimensions = asRecord(coaching.dimensions) || {};
  const dimensionNotes: string[] = [];
  for (const [key, value] of Object.entries(dimensions)) {
    const row = asRecord(value);
    if (!row) {
      continue;
    }
    const insight = String(row.insight || "").trim();
    const action = String(row.action || "").trim();
    const status = String(row.status || "").trim();
    const label = key.replace(/_/g, " ");
    const text = `${label}: ${status}${insight ? ` | ${insight}` : ""}${action ? ` | action: ${action}` : ""}`;
    if (text.trim()) {
      dimensionNotes.push(text.trim());
    }
  }
  const watchOut = String(coaching.watch_out || "").trim();
  return {
    healthScore: parseNumberOrNull(coaching.overall_health_score),
    healthGrade: String(coaching.health_grade || "").trim(),
    topPriorities: parseStringArray(coaching.top_priorities),
    quickWins: parseStringArray(coaching.quick_wins),
    watchOuts: watchOut ? [watchOut] : [],
    dimensionNotes,
  };
}

function parseStrategyPulseSummary(raw: unknown): StrategyPulseSummary {
  const payload = asRecord(raw) || ({} as Record<string, unknown>);
  const burnout = asRecord(payload.burnout_snapshot);
  const outlook = asRecord(payload.predictive_outlook);
  const strategyGaps = Array.isArray(payload.strategy_gaps)
    ? payload.strategy_gaps
        .map((row) => asRecord(row))
        .filter((row): row is Record<string, unknown> => Boolean(row))
    : [];
  const gapSignalsFromRows = strategyGaps
    .slice(0, 5)
    .map((gap) => {
      const title = String(gap.title || "Untitled").trim();
      const gapType = String(gap.gap_type || "N/A").trim();
      const severity = Number(gap.severity || 0);
      return `${title}: ${gapType} (severity ${Math.round(severity)})`;
    })
    .filter(Boolean);
  const mitigationSteps = parseStringArray(outlook?.risk_mitigation);
  const strategicPivots = parseStringArray(outlook?.strategic_pivots);
  const portfolioActions = parseStringArray(payload.portfolio_actions);
  const confidenceLevel = parseNumberOrNull(outlook?.confidence_level);
  return {
    burnoutRisk: String(payload.burnout_risk || burnout?.risk_label || "").trim(),
    burnoutScore: parseNumberOrNull(burnout?.risk_score),
    avgDailyMinutes: parseNumberOrNull(burnout?.avg_daily_minutes),
    completedTasks14d: parseNumberOrNull(burnout?.completed_tasks),
    gapSignals: parseStringArray(payload.gap_signals).length
      ? parseStringArray(payload.gap_signals)
      : gapSignalsFromRows,
    predictiveOutlook: String(payload.predictive_outlook || outlook?.outlook_summary || "").trim(),
    confidenceLevel,
    mitigationSteps,
    strategicPivots,
    portfolioActions: portfolioActions.length ? portfolioActions : [...mitigationSteps, ...strategicPivots],
  };
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function normalizedMindmapType(raw: unknown): MindmapTreeNode["type"] {
  const text = String(raw || "").trim().toUpperCase();
  if (text === "GOAL" || text === "OBJECTIVE" || text === "KEY_RESULT" || text === "TASK") {
    return text;
  }
  return "NODE";
}

function inferChildType(parentType: MindmapTreeNode["type"]): MindmapTreeNode["type"] {
  if (parentType === "GOAL") {
    return "OBJECTIVE";
  }
  if (parentType === "OBJECTIVE") {
    return "KEY_RESULT";
  }
  if (parentType === "KEY_RESULT") {
    return "TASK";
  }
  return "NODE";
}

function buildMindmapTree(nodeRaw: unknown, nodeTypeRaw?: unknown): MindmapTreeNode | null {
  const node = asRecord(nodeRaw);
  if (!node) {
    return null;
  }
  const type = normalizedMindmapType(node.__tablename__ || nodeTypeRaw || node.node_type || node.type);
  const idRaw = Number(node.id);
  const id = Number.isFinite(idRaw) ? idRaw : null;
  const title = String(node.title || `${type}${id ? ` #${id}` : ""}` || "Node").trim();
  const progress = parseNumberOrNull(node.progress);
  const childType = inferChildType(type);
  const childrenRaw =
    (Array.isArray(node.objectives) ? node.objectives : null) ||
    (Array.isArray(node.key_results) ? node.key_results : null) ||
    (Array.isArray(node.tasks) ? node.tasks : null) ||
    [];
  const children = childrenRaw
    .map((item) => buildMindmapTree(item, childType))
    .filter((item): item is MindmapTreeNode => Boolean(item));
  return {
    id,
    type,
    title,
    progress,
    children,
  };
}

function isGenericIndexedTitle(
  title: string,
  nodeType: AtlasIndexNode["type"],
  nodeId: number,
): boolean {
  const normalized = String(title || "").trim().toLowerCase();
  if (!normalized) {
    return true;
  }
  const safeId = Number(nodeId);
  if (!Number.isFinite(safeId) || safeId <= 0) {
    return false;
  }
  const typeToken = nodeType.replace(/_/g, " ").toLowerCase();
  const labelToken = nodeTypeLabel(nodeType).toLowerCase();
  const id = Math.round(safeId);
  const fallbackTokens = new Set([
    `${typeToken} #${id}`,
    `${typeToken} ${id}`,
    `${typeToken}#${id}`,
    `${labelToken} #${id}`,
    `${labelToken} ${id}`,
    `${labelToken}#${id}`,
  ]);
  return fallbackTokens.has(normalized);
}

function findMindmapNodeTitle(
  root: MindmapTreeNode | null,
  nodeType: AtlasIndexNode["type"],
  nodeId: number,
): string {
  if (!root) {
    return "";
  }
  const stack: MindmapTreeNode[] = [root];
  while (stack.length) {
    const current = stack.pop();
    if (!current) {
      continue;
    }
    if (current.type === nodeType && current.id === nodeId) {
      return String(current.title || "").trim();
    }
    for (const child of current.children) {
      stack.push(child);
    }
  }
  return "";
}

function buildTeamCoachBaseline(metrics: LeadershipMetricsResponse | null): TeamCoachSummary {
  const hygiene = Math.max(0, Math.min(100, Number(metrics?.hygiene_pct || 0)));
  const avgConfidence10 = Math.max(0, Math.min(10, Number(metrics?.avg_confidence || 0)));
  const totalKrs = Math.max(0, Number(metrics?.total_krs || 0));
  const atRiskCount = Math.max(0, Number(metrics?.at_risk_count || 0));
  const riskRatio = totalKrs > 0 ? atRiskCount / totalKrs : 0;
  const riskScore = 100 - Math.round(riskRatio * 100);
  const confidenceScore = Math.round(avgConfidence10 * 10);
  const healthScore = Math.max(
    0,
    Math.min(100, Math.round(hygiene * 0.35 + confidenceScore * 0.25 + riskScore * 0.4)),
  );
  const healthGrade = healthScore >= 85 ? "A" : healthScore >= 70 ? "B" : healthScore >= 55 ? "C" : healthScore >= 40 ? "D" : "F";

  const topPriorities: string[] = [];
  if (atRiskCount > 0) {
    topPriorities.push(`Recover ${atRiskCount} at-risk key results with focused owner interventions.`);
  }
  if (hygiene < 70) {
    topPriorities.push("Improve weekly check-in hygiene to stabilize decision quality.");
  }
  if (avgConfidence10 < 5) {
    topPriorities.push("Raise confidence through tighter KR evidence and coaching cadence.");
  }
  if (!topPriorities.length) {
    topPriorities.push("Maintain current execution cadence and guard against regression.");
  }

  const quickWins: string[] = [];
  if (hygiene < 85) {
    quickWins.push("Run a 30-minute check-in completion sweep for stale KRs.");
  }
  if (avgConfidence10 < 7) {
    quickWins.push("Require concise evidence notes on each check-in update.");
  }
  if (!quickWins.length) {
    quickWins.push("Promote top-performing playbooks across team members.");
  }

  const atRiskRows = Array.isArray(metrics?.at_risk) ? metrics?.at_risk : [];
  const watchOuts = atRiskRows
    .slice(0, 3)
    .map((row) => String((row as Record<string, unknown>).reason || "").trim())
    .filter(Boolean);

  const dimensionNotes = [
    `Productivity signal: ${(Array.isArray(metrics?.member_progress) ? metrics?.member_progress.length : 0)} members tracked.`,
    `Deadline discipline: ${atRiskCount}/${Math.max(totalKrs, 1)} KRs at risk.`,
    `Strategic alignment: hygiene ${Math.round(hygiene)}%, confidence ${avgConfidence10.toFixed(1)}/10.`,
  ];

  return {
    healthScore,
    healthGrade,
    topPriorities,
    quickWins,
    watchOuts,
    dimensionNotes,
  };
}

function buildStrategyPulseBaseline(metrics: LeadershipMetricsResponse | null): StrategyPulseSummary {
  const avgConfidence10 = Math.max(0, Math.min(10, Number(metrics?.avg_confidence || 0)));
  const hygiene = Math.max(0, Math.min(100, Number(metrics?.hygiene_pct || 0)));
  const totalKrs = Math.max(0, Number(metrics?.total_krs || 0));
  const atRiskCount = Math.max(0, Number(metrics?.at_risk_count || 0));
  const riskRatio = totalKrs > 0 ? atRiskCount / totalKrs : 0;

  let burnoutRisk = "Healthy";
  if (riskRatio > 0.45 || avgConfidence10 < 4) {
    burnoutRisk = "Critical";
  } else if (riskRatio > 0.3 || avgConfidence10 < 5) {
    burnoutRisk = "High";
  } else if (riskRatio > 0.15 || avgConfidence10 < 6.5) {
    burnoutRisk = "Elevated";
  }

  const atRiskRows = Array.isArray(metrics?.at_risk) ? metrics?.at_risk : [];
  const gapSignals = atRiskRows
    .slice(0, 5)
    .map((row) => {
      const item = row as Record<string, unknown>;
      return `${String(item.title || "KR").trim()}: ${String(item.reason || "Needs review").trim()}`;
    })
    .filter(Boolean);

  const predictiveOutlook =
    burnoutRisk === "Healthy"
      ? "Current trajectory is stable if check-in hygiene remains consistent."
      : burnoutRisk === "Elevated"
        ? "Trajectory is mixed; prioritize short-cycle risk mitigation on exposed KRs."
        : burnoutRisk === "High"
          ? "Delivery risk is rising; rebalance workload and narrow active commitments."
          : "Critical delivery pressure detected; immediate scope triage is required.";

  const portfolioActions = [
    hygiene < 75 ? "Increase evidence-backed check-ins to improve portfolio traceability." : "Preserve high-quality evidence flow for completed outcomes.",
    atRiskCount > 0 ? "Package recovered at-risk KR turnarounds as leadership case studies." : "Promote completed KR patterns as repeatable strategic playbooks.",
  ];

  return {
    burnoutRisk,
    burnoutScore: Math.round(riskRatio * 100),
    avgDailyMinutes: null,
    completedTasks14d: null,
    gapSignals,
    predictiveOutlook,
    confidenceLevel: null,
    mitigationSteps: [],
    strategicPivots: [],
    portfolioActions,
  };
}

function startOfWeekIso(today = new Date()): string {
  const date = new Date(today);
  const day = date.getDay();
  const delta = day === 0 ? -6 : 1 - day;
  date.setDate(date.getDate() + delta);
  return `${date.getFullYear()}-${`${date.getMonth() + 1}`.padStart(2, "0")}-${`${date.getDate()}`.padStart(2, "0")}`;
}

function endOfWeekIso(today = new Date()): string {
  const start = new Date(`${startOfWeekIso(today)}T00:00:00`);
  start.setDate(start.getDate() + 6);
  return `${start.getFullYear()}-${`${start.getMonth() + 1}`.padStart(2, "0")}-${`${start.getDate()}`.padStart(2, "0")}`;
}

export default function AtlasShell() {
  const router = useRouter();
  const [cycleId, setCycleId] = useState("");
  const [resolvedCycle, setResolvedCycle] = useState<ResolvedCycle | null>(null);
  const [cycleResolvePending, setCycleResolvePending] = useState(false);
  const [cycleResolveError, setCycleResolveError] = useState("");
  const [sessionCycles, setSessionCycles] = useState<CycleSummary[]>([]);
  const [adminCycles, setAdminCycles] = useState<CycleSummary[]>([]);
  const [adminCyclesPending, setAdminCyclesPending] = useState(false);
  const [adminCycleMessage, setAdminCycleMessage] = useState("");
  const [adminCycleError, setAdminCycleError] = useState("");
  const [adminTab, setAdminTab] = useState<AdminTab>("cycles");
  const [adminUsers, setAdminUsers] = useState<AdminUserRead[]>([]);
  const [adminTeams, setAdminTeams] = useState<AdminTeamRead[]>([]);
  const [adminDataPending, setAdminDataPending] = useState(false);
  const [adminDataError, setAdminDataError] = useState("");
  const [adminUserDraft, setAdminUserDraft] = useState<AdminUserDraft>({
    username: "",
    displayName: "",
    password: "",
    role: "member",
    managerId: "",
    teamId: "",
    mustChangePassword: true,
  });
  const [adminTeamDraft, setAdminTeamDraft] = useState<AdminTeamDraft>({
    name: "",
    description: "",
  });
  const [adminResetDraft, setAdminResetDraft] = useState<AdminResetDraft>({
    userId: "",
    newPassword: "",
    requireChange: false,
  });
  const [adminAiHealth, setAdminAiHealth] = useState<AdminAiHealthResponse | null>(null);
  const [adminPdfHealth, setAdminPdfHealth] = useState<AdminPdfHealthResponse | null>(null);
  const [adminBackupFile, setAdminBackupFile] = useState<File | null>(null);
  const [adminBackupConfirm, setAdminBackupConfirm] = useState("");
  const [adminBackupRestoreResult, setAdminBackupRestoreResult] = useState<AdminDbRestoreResponse | null>(null);
  const [adminHealthPending, setAdminHealthPending] = useState(false);
  const [adminBackupPending, setAdminBackupPending] = useState(false);
  const [adminCreateCycleDraft, setAdminCreateCycleDraft] = useState<AdminCreateCycleDraft>({
    title: "",
    startDate: "",
    endDate: "",
    isActive: false,
  });
  const [mode, setMode] = useState(DEFAULT_MODE);
  const [modeDataPending, setModeDataPending] = useState(false);
  const [modeDataError, setModeDataError] = useState("");
  const dashboardRefreshInFlightRef = useRef(false);
  const [weeklyPlanData, setWeeklyPlanData] = useState<WeeklyPlanRead | null>(null);
  const [weeklyLogs, setWeeklyLogs] = useState<WorkLogRead[]>([]);
  const [weeklyKrsNeedingCheckIn, setWeeklyKrsNeedingCheckIn] = useState<KeyResultRead[]>([]);
  const [weeklyReviewExperiments, setWeeklyReviewExperiments] = useState<ExperimentRead[]>([]);
  const [dailyLogs, setDailyLogs] = useState<WorkLogRead[]>([]);
  const [dailyLogQuery, setDailyLogQuery] = useState("");
  const [ritualStep, setRitualStep] = useState<1 | 2 | 3>(1);
  const [ritualKrs, setRitualKrs] = useState<KeyResultRead[]>([]);
  const [ritualExperimentsByKr, setRitualExperimentsByKr] = useState<Record<number, ExperimentRead[]>>({});
  const [ritualReviewExperiments, setRitualReviewExperiments] = useState<ExperimentRead[]>([]);
  const [ritualReviewLogs, setRitualReviewLogs] = useState<WorkLogRead[]>([]);
  const [retroItems, setRetroItems] = useState<RetroRead[]>([]);
  const [timelineTasks, setTimelineTasks] = useState<TimelineTaskRead[]>([]);
  const [timelineLogs, setTimelineLogs] = useState<WorkLogRead[]>([]);
  const [timelineQuery, setTimelineQuery] = useState("");
  const [timelineStatusFilter, setTimelineStatusFilter] = useState<
    "all" | "todo" | "in_progress" | "done" | "blocked" | "overdue"
  >("all");
  const [leadershipMetrics, setLeadershipMetrics] = useState<LeadershipMetricsResponse | null>(null);
  const [leadershipPending, setLeadershipPending] = useState(false);
  const [leadershipError, setLeadershipError] = useState("");
  const [teamCoachPending, setTeamCoachPending] = useState(false);
  const [teamCoachError, setTeamCoachError] = useState("");
  const [teamCoachSummary, setTeamCoachSummary] = useState<TeamCoachSummary | null>(null);
  const [strategyPulsePending, setStrategyPulsePending] = useState(false);
  const [strategyPulseError, setStrategyPulseError] = useState("");
  const [strategyPulseSummary, setStrategyPulseSummary] = useState<StrategyPulseSummary | null>(null);
  const [weeklyDraft, setWeeklyDraft] = useState({ p1: "", p2: "", p3: "" });
  const [retroDraft, setRetroDraft] = useState({ content: "", sentiment: "" });
  const [modeActionPending, setModeActionPending] = useState(false);
  const [modeActionMessage, setModeActionMessage] = useState("");
  const [modeActionError, setModeActionError] = useState("");
  const [reportExportPending, setReportExportPending] = useState(false);
  const [reportExportError, setReportExportError] = useState("");
  const [reportAiPending, setReportAiPending] = useState(false);
  const [reportAiError, setReportAiError] = useState("");
  const [reportAiSummary, setReportAiSummary] = useState<ReportAiSummary | null>(null);
  const [ritualCheckInDrafts, setRitualCheckInDrafts] = useState<Record<number, CheckInDraft>>({});
  const [ritualExperimentDrafts, setRitualExperimentDrafts] = useState<Record<number, ExperimentDraft>>({});
  const [ritualExperimentFormOpen, setRitualExperimentFormOpen] = useState<Record<number, boolean>>({});
  const [ritualExperimentPending, setRitualExperimentPending] = useState<Record<number, boolean>>({});
  const [ritualExperimentError, setRitualExperimentError] = useState<Record<number, string>>({});
  const [ritualExperimentMessage, setRitualExperimentMessage] = useState<Record<number, string>>({});
  const [ritualExperimentCloseDrafts, setRitualExperimentCloseDrafts] = useState<
    Record<number, ExperimentCloseDraft>
  >({});
  const [ritualExperimentActionPending, setRitualExperimentActionPending] = useState<
    Record<number, boolean>
  >({});
  const [ritualExperimentActionError, setRitualExperimentActionError] = useState<
    Record<number, string>
  >({});
  const [ritualExperimentActionMessage, setRitualExperimentActionMessage] = useState<
    Record<number, string>
  >({});
  const [ritualCheckInPending, setRitualCheckInPending] = useState<Record<number, boolean>>({});
  const [ritualCheckInError, setRitualCheckInError] = useState<Record<number, string>>({});
  const [ritualCheckInMessage, setRitualCheckInMessage] = useState<Record<number, string>>({});
  const [aiSyncPending, setAiSyncPending] = useState(false);
  const [aiSyncError, setAiSyncError] = useState("");
  const [aiSyncMessage, setAiSyncMessage] = useState("");
  const [aiSyncReport, setAiSyncReport] = useState<AiSyncReport | null>(null);
  const [aiProgressUndoItems, setAiProgressUndoItems] = useState<AiProgressUndoItem[]>([]);
  const [aiSuggestPending, setAiSuggestPending] = useState(false);
  const [aiSuggestion, setAiSuggestion] = useState<AiTaskSuggestion | null>(null);
  const [mindmapPayload, setMindmapPayload] = useState<Record<string, unknown> | null>(null);
  const [mindmapPending, setMindmapPending] = useState(false);
  const [mindmapError, setMindmapError] = useState("");
  const [lens, setLens] = useState(DEFAULT_LENS);
  const [ownerIdsInput, setOwnerIdsInput] = useState("");
  const [nodeQuery, setNodeQuery] = useState("");
  const [selectedRef, setSelectedRef] = useState("");
  const [focusTaskRef, setFocusTaskRef] = useState("");
  const [previewBypass, setPreviewBypass] = useState(false);
  const [deepLinkReady, setDeepLinkReady] = useState(false);
  const [rolloutConfig, setRolloutConfig] = useState<SpaRolloutConfig | null>(null);
  const [authHydrated, setAuthHydrated] = useState(false);
  const [snapshotPending, setSnapshotPending] = useState(false);
  const [timerPending, setTimerPending] = useState(false);
  const [timerSummary, setTimerSummary] = useState("");
  const [timerError, setTimerError] = useState("");
  const [timerMessage, setTimerMessage] = useState("");
  const [timerModalOpen, setTimerModalOpen] = useState(false);
  const [timerSessionStartAt, setTimerSessionStartAt] = useState("");
  const [timerSessionTaskId, setTimerSessionTaskId] = useState<number | null>(null);
  const [timerClockNowMs, setTimerClockNowMs] = useState(() => Date.now());
  const [inspectPending, setInspectPending] = useState(false);
  const [inspectError, setInspectError] = useState("");
  const [inspectMessage, setInspectMessage] = useState("");
  const [inspectAnalysisPending, setInspectAnalysisPending] = useState(false);
  const [inspectAnalysisError, setInspectAnalysisError] = useState("");
  const [inspectAnalysis, setInspectAnalysis] = useState<AnalysisSummary | null>(null);
  const [inspectDraft, setInspectDraft] = useState<InspectorEditDraft>({
    title: "",
    description: "",
    progress: "",
  });
  const [createPending, setCreatePending] = useState(false);
  const [createError, setCreateError] = useState("");
  const [createMessage, setCreateMessage] = useState("");
  const [createDraft, setCreateDraft] = useState<NodeCreateDraft>({
    createType: "objective",
    title: "",
    description: "",
    cycleId: "",
    tags: "",
    targetValue: "100",
    unit: "%",
    estimatedMinutes: "30",
    assigneeId: "",
  });
  const [deletePending, setDeletePending] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const [deleteMessage, setDeleteMessage] = useState("");
  const [snapshotError, setSnapshotError] = useState("");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [snapshotPayload, setSnapshotPayload] = useState<AtlasSnapshotResponse | null>(null);

  const parsedCycleId = useMemo(() => {
    const parsed = Number.parseInt(cycleId, 10);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  }, [cycleId]);
  const ritualReviewRange = useMemo(() => reviewWindow(), []);

  useEffect(() => {
    if (parsedCycleId) {
      setCycleResolveError("");
      if (!resolvedCycle || resolvedCycle.id !== parsedCycleId) {
        setResolvedCycle({ id: parsedCycleId, title: "" });
      }
    }
  }, [parsedCycleId, resolvedCycle]);

  useEffect(() => {
    setAiSyncReport(null);
    setAiProgressUndoItems([]);
    setAiSuggestion(null);
    setAiSyncError("");
    setAiSyncMessage("");
    setReportAiSummary(null);
    setReportAiError("");
  }, [parsedCycleId]);

  useEffect(() => {
    if (mode !== "weekly" && mode !== "daily") {
      setReportAiSummary(null);
      setReportAiError("");
    }
  }, [mode]);

  useEffect(() => {
    if (mode !== "dashboard") {
      setTeamCoachSummary(null);
      setTeamCoachError("");
      setStrategyPulseSummary(null);
      setStrategyPulseError("");
    }
  }, [mode]);

  useEffect(() => {
    if (mode !== "timeline") {
      setTimelineQuery("");
      setTimelineStatusFilter("all");
    }
  }, [mode]);

  useEffect(() => {
    if (mode !== "daily") {
      setDailyLogQuery("");
    }
  }, [mode]);

  useEffect(() => {
    if (mode !== "ritual") {
      return;
    }
    setRitualStep(1);
  }, [mode]);

  useEffect(() => {
    if (mode !== "dashboard" || !leadershipMetrics) {
      return;
    }
    setTeamCoachSummary((prev) => prev || buildTeamCoachBaseline(leadershipMetrics));
    setStrategyPulseSummary((prev) => prev || buildStrategyPulseBaseline(leadershipMetrics));
  }, [leadershipMetrics, mode]);

  useEffect(() => {
    if (!user || !parsedCycleId) {
      return;
    }
    if (
      resolvedCycle &&
      resolvedCycle.id === parsedCycleId &&
      (Boolean(cyclePeriodLabel(resolvedCycle)) || Boolean(String(resolvedCycle.title || "").trim()))
    ) {
      return;
    }

    const cachedMatch = sessionCycles.find((cycle) => cycle.id === parsedCycleId);
    if (cachedMatch) {
      setResolvedCycle({
        id: cachedMatch.id,
        title: cachedMatch.title,
        start_date: cachedMatch.start_date || null,
        end_date: cachedMatch.end_date || null,
      });
      return;
    }

    let active = true;
    void (async () => {
      try {
        const cycles = await readCyclesQuery({
          actor_username: user.username,
          kind: "cycles.all",
        });
        if (!active) {
          return;
        }
        setSessionCycles([...cycles].sort((left, right) => right.id - left.id));
        const matched = cycles.find((cycle) => cycle.id === parsedCycleId);
        if (!matched) {
          return;
        }
        setResolvedCycle({
          id: matched.id,
          title: matched.title,
          start_date: matched.start_date || null,
          end_date: matched.end_date || null,
        });
      } catch {
        // keep current resolved cycle fallback
      }
    })();
    return () => {
      active = false;
    };
  }, [parsedCycleId, resolvedCycle, sessionCycles, user]);

  const parsedOwnerIds = useMemo(() => parseOwnerIds(ownerIdsInput), [ownerIdsInput]);

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
      cycle: cycleId,
      mode,
      sel: selectedRef,
      ft: focusTaskRef,
      lens,
    });
    const params = new URLSearchParams(baseQuery);
    if (previewBypass) {
      params.set("spa_preview", "1");
    }
    return params.toString();
  }, [cycleId, mode, selectedRef, focusTaskRef, lens, previewBypass]);

  function handleSidebarModeSelect(nextMode: string): void {
    const routePath = pathForMode(nextMode);
    const query = buildDeepLinkQuery({
      cycle: cycleId,
      mode: nextMode,
      sel: selectedRef,
      ft: focusTaskRef,
      lens,
    });
    const nextUrl = query ? `${routePath}?${query}` : routePath;
    router.replace(nextUrl);
    setMode(nextMode);
  }

  const filteredRefs = useMemo(() => {
    if (!atlasRuntime) {
      return [];
    }
    const query = nodeQuery.trim().toLowerCase();
    if (!query) {
      return allScopeRefs;
    }
    return allScopeRefs.filter((ref) => {
      const meta = atlasRuntime.index[ref];
      if (!meta) {
        return false;
      }
      return (
        meta.titleLower.includes(query) ||
        meta.description.toLowerCase().includes(query) ||
        meta.ownerName.toLowerCase().includes(query) ||
        meta.ref.includes(query)
      );
    });
  }, [allScopeRefs, atlasRuntime, nodeQuery]);

  const selectedMeta = useMemo(() => {
    if (!atlasRuntime || !selectedRef) {
      return null;
    }
    return atlasRuntime.index[selectedRef] || null;
  }, [atlasRuntime, selectedRef]);

  const createContext = useMemo(() => {
    return {
      goalId: nearestAncestorId(selectedMeta, atlasRuntime?.index || null, "GOAL"),
      objectiveId: nearestAncestorId(selectedMeta, atlasRuntime?.index || null, "OBJECTIVE"),
      keyResultId: nearestAncestorId(selectedMeta, atlasRuntime?.index || null, "KEY_RESULT"),
    };
  }, [atlasRuntime, selectedMeta]);

  const canCreateForContext = useMemo(() => {
    if (createDraft.createType === "goal") {
      return true;
    }
    if (createDraft.createType === "objective") {
      return Boolean(createContext.goalId);
    }
    if (createDraft.createType === "key_result") {
      return Boolean(createContext.objectiveId);
    }
    return Boolean(createContext.keyResultId);
  }, [createContext.goalId, createContext.keyResultId, createContext.objectiveId, createDraft.createType]);

  const rolloutDecision = useMemo<RolloutDecision>(() => {
    if (!rolloutConfig) {
      return { allowed: false, reason: "disabled" };
    }
    return evaluateSpaRollout(user, rolloutConfig, { previewBypass });
  }, [rolloutConfig, user, previewBypass]);
  const rolloutMessage = useMemo(
    () => rolloutReasonMessage(rolloutDecision.reason),
    [rolloutDecision.reason],
  );

  const rolloutAllowed = Boolean(rolloutConfig && rolloutDecision.allowed);
  const isAdmin = String(user?.role || "").trim().toLowerCase() === "admin";
  const sidebarItems = useMemo(
    () => (isAdmin ? SIDEBAR_ITEMS : SIDEBAR_ITEMS.filter((item) => item.mode !== "admin")),
    [isAdmin],
  );
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
    rolloutAllowed,
    parsedCycleId,
    loadSnapshotForUser,
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

  const focusTaskRunning = useMemo(() => {
    if (String(timerSessionStartAt || "").trim()) {
      return true;
    }
    if (!focusTaskMeta || focusTaskMeta.type !== "TASK") {
      return false;
    }
    const task = focusTaskMeta.node as AtlasTaskSnapshot;
    return Boolean(task.timer_started_at);
  }, [focusTaskMeta, timerSessionStartAt]);

  const activeTimerStartedAt = useMemo(() => {
    const explicit = String(timerSessionStartAt || "").trim();
    if (explicit) {
      return explicit;
    }
    if (focusTaskMeta && focusTaskMeta.type === "TASK") {
      const task = focusTaskMeta.node as AtlasTaskSnapshot;
      return String(task.timer_started_at || "").trim();
    }
    return "";
  }, [focusTaskMeta, timerSessionStartAt]);

  const activeTimerElapsedSeconds = useMemo(() => {
    const parsed = parseDateOrNull(activeTimerStartedAt);
    if (!parsed) {
      return 0;
    }
    return Math.max(0, Math.floor((timerClockNowMs - parsed.getTime()) / 1000));
  }, [activeTimerStartedAt, timerClockNowMs]);

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

  useEffect(() => {
    if (!ritualKrs.length) {
      setRitualCheckInDrafts({});
      return;
    }
    setRitualCheckInDrafts((prev) => {
      const next: Record<number, CheckInDraft> = {};
      for (const kr of ritualKrs) {
        const krId = Number(kr.id);
        if (!Number.isFinite(krId) || krId <= 0) {
          continue;
        }
        const existing = prev[krId];
        if (existing) {
          next[krId] = existing;
          continue;
        }
        const currentValue = parseNumberOrNull(kr.current_value);
        const fallbackValue = parseNumberOrNull(kr.progress);
        next[krId] = {
          value: `${currentValue ?? fallbackValue ?? 0}`,
          confidence: "7",
          comment: "",
          variationType: "COMMON_CAUSE",
          specialCauseNote: "",
          experimentId: "",
        };
      }
      return next;
    });
  }, [ritualKrs]);

  useEffect(() => {
    if (!selectedMeta) {
      setInspectAnalysis(null);
      setInspectAnalysisError("");
      return;
    }
    if (selectedMeta.type === "KEY_RESULT") {
      const keyResult = selectedMeta.node as AtlasKeyResultSnapshot;
      setInspectAnalysis(parseAnalysisSummary(keyResult.gemini_analysis || null));
      setInspectAnalysisError("");
      return;
    }
    setInspectAnalysis(null);
    setInspectAnalysisError("");
  }, [selectedMeta]);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const sessionUser = await readSessionUser();
        if (!active) {
          return;
        }
        setUser(sessionUser);
      } catch {
        if (!active) {
          return;
        }
        setUser(null);
      } finally {
        if (active) {
          setAuthHydrated(true);
        }
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!authHydrated || user) {
      return;
    }
    const returnTo =
      typeof window === "undefined" ? "/" : `${window.location.pathname}${window.location.search}`;
    router.replace(`/login?return_to=${encodeURIComponent(returnTo)}`);
  }, [authHydrated, router, user]);

  useEffect(() => {
    if (!user) {
      return;
    }
    if (!isAdmin && mode === "admin") {
      handleSidebarModeSelect("atlas");
    }
  }, [isAdmin, mode, user]);

  useEffect(() => {
    let active = true;

    void (async () => {
      try {
        const config = await readSpaRolloutConfig();
        if (!active) {
          return;
        }
        setRolloutConfig(config);
      } catch (error) {
        if (!active) {
          return;
        }
        setRolloutConfig(null);
      }
    })();

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const syncFromLocation = () => {
      const parsed = parseDeepLink(window.location.search);
      const pathMode = modeForPath(window.location.pathname);
      setPreviewBypass(parsePreviewBypass(window.location.search));
      if (parsed.cycle) {
        setResolvedCycle(null);
        setCycleId(parsed.cycle);
      }
      setMode(parsed.mode || pathMode || DEFAULT_MODE);
      setLens(parsed.lens || DEFAULT_LENS);
      if (parsed.sel) {
        setSelectedRef(parsed.sel);
      }
      if (parsed.ft) {
        setFocusTaskRef(normalizeFocusTaskRef(parsed.ft));
      }
      setDeepLinkReady(true);
    };

    syncFromLocation();
    window.addEventListener("popstate", syncFromLocation);
    return () => {
      window.removeEventListener("popstate", syncFromLocation);
    };
  }, []);

  useEffect(() => {
    if (!user || !deepLinkReady || parsedCycleId) {
      return;
    }
    let active = true;
    setCycleResolvePending(true);
    setCycleResolveError("");

    const pickCycle = (cycles: CycleSummary[]): CycleSummary | null => {
      if (!cycles.length) {
        return null;
      }
      const explicitActive = cycles.find((cycle) => Boolean(cycle.is_active));
      if (explicitActive) {
        return explicitActive;
      }
      return [...cycles].sort((left, right) => right.id - left.id)[0] || null;
    };

    void (async () => {
      try {
        const activeCycles = await readCyclesQuery({
          actor_username: user.username,
          kind: "cycles.active",
        });
        if (!active) {
          return;
        }
        const sortedActive = [...activeCycles].sort((left, right) => right.id - left.id);
        const selectedActive = pickCycle(sortedActive);
        if (selectedActive) {
          setSessionCycles(sortedActive);
          setResolvedCycle({
            id: selectedActive.id,
            title: selectedActive.title,
            start_date: selectedActive.start_date || null,
            end_date: selectedActive.end_date || null,
          });
          setCycleId(String(selectedActive.id));
          void (async () => {
            try {
              const allCycles = await readCyclesQuery({
                actor_username: user.username,
                kind: "cycles.all",
              });
              if (!active) {
                return;
              }
              setSessionCycles([...allCycles].sort((left, right) => right.id - left.id));
            } catch {
              // keep active-cycle bootstrap state if full list hydration fails
            }
          })();
          return;
        }

        const cycles = await readCyclesQuery({
          actor_username: user.username,
          kind: "cycles.all",
        });
        if (!active) {
          return;
        }
        const sorted = [...cycles].sort((left, right) => right.id - left.id);
        setSessionCycles(sorted);
        const selected = pickCycle(sorted);
        if (!selected) {
          setCycleResolveError("No cycle found. Create or activate a cycle to load Atlas snapshot.");
          setResolvedCycle(null);
          return;
        }
        setResolvedCycle({
          id: selected.id,
          title: selected.title,
          start_date: selected.start_date || null,
          end_date: selected.end_date || null,
        });
        setCycleId(String(selected.id));
      } catch (error) {
        if (!active) {
          return;
        }
        setResolvedCycle(null);
        setCycleResolveError(
          `Could not auto-detect active cycle: ${String(error instanceof Error ? error.message : error)}`,
        );
      } finally {
        if (active) {
          setCycleResolvePending(false);
        }
      }
    })();

    return () => {
      active = false;
    };
  }, [deepLinkReady, parsedCycleId, user]);

  useEffect(() => {
    if (!atlasRuntime || atlasRuntime.roots.length === 0) {
      if (selectedRef) {
        setSelectedRef("");
      }
      return;
    }

    if (!selectedRef || !atlasRuntime.index[selectedRef]) {
      setSelectedRef(atlasRuntime.roots[0]);
    }
  }, [atlasRuntime, selectedRef]);

  useEffect(() => {
    if (!taskRefs.length) {
      if (focusTaskRef) {
        setFocusTaskRef("");
      }
      return;
    }
    if (focusTaskRef && !taskRefs.includes(focusTaskRef)) {
      setFocusTaskRef("");
    }
  }, [focusTaskRef, taskRefs]);

  useEffect(() => {
    if (selectedMeta?.type === "TASK" && selectedMeta.ref !== focusTaskRef) {
      setFocusTaskRef(selectedMeta.ref);
    }
  }, [selectedMeta, focusTaskRef]);

  useEffect(() => {
    if (!focusTaskMeta || !focusTaskRunning) {
      return;
    }
    if (!timerSessionTaskId) {
      setTimerSessionTaskId(focusTaskMeta.id);
    }
  }, [focusTaskMeta, focusTaskRunning, timerSessionTaskId]);

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

  useEffect(() => {
    if (!selectedMeta) {
      setInspectDraft({
        title: "",
        description: "",
        progress: "",
      });
      setCreateError("");
      setCreateMessage("");
      setDeleteError("");
      setDeleteMessage("");
      return;
    }
    setInspectDraft({
      title: selectedMeta.title,
      description: selectedMeta.description,
      progress: `${selectedMeta.progress}`,
    });
    setCreateDraft((prev) => ({
      ...prev,
      createType:
        selectedMeta.type === "GOAL"
          ? "objective"
          : selectedMeta.type === "OBJECTIVE"
            ? "key_result"
            : selectedMeta.type === "KEY_RESULT"
              ? "task"
              : "task",
    }));
    setInspectError("");
    setInspectMessage("");
    setCreateError("");
    setCreateMessage("");
    setDeleteError("");
    setDeleteMessage("");
  }, [selectedMeta]);

  useEffect(() => {
    if (!user || !selectedMeta) {
      setMindmapPayload(null);
      return;
    }
    void loadMindmap(user, selectedMeta.id, selectedMeta.type);
  }, [selectedMeta, user]);

  useEffect(() => {
    setCreateDraft((prev) => {
      if (prev.cycleId.trim()) {
        return prev;
      }
      return {
        ...prev,
        cycleId: cycleId,
      };
    });
  }, [cycleId]);

  useEffect(() => {
    if (!deepLinkReady || typeof window === "undefined") {
      return;
    }
    const nextSearch = deepLinkQuery ? `?${deepLinkQuery}` : "";
    if (window.location.search === nextSearch) {
      return;
    }
    const nextUrl = `${window.location.pathname}${nextSearch}${window.location.hash}`;
    window.history.replaceState(null, "", nextUrl);
  }, [deepLinkQuery, deepLinkReady]);

  useEffect(() => {
    if (!user || !parsedCycleId || parsedOwnerIds.error || !rolloutAllowed) {
      if (!parsedCycleId || parsedOwnerIds.error || !rolloutAllowed) {
        setSnapshotPayload(null);
      }
      setSnapshotPending(false);
      return;
    }

    let active = true;
    setSnapshotPending(true);
    setSnapshotError("");

    const timer = window.setTimeout(() => {
      void (async () => {
        try {
          await loadSnapshotForUser(user);
        } catch (error) {
          if (!active) {
            return;
          }
          setSnapshotError(String(error instanceof Error ? error.message : error));
          setSnapshotPayload(null);
        } finally {
          if (active) {
            setSnapshotPending(false);
          }
        }
      })();
    }, 200);

    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [parsedCycleId, parsedOwnerIds.error, parsedOwnerIds.value, rolloutAllowed, user]);

  useEffect(() => {
    if (!user || mode !== "atlas" || !parsedCycleId || parsedOwnerIds.error || !rolloutAllowed) {
      return;
    }

    let active = true;
    const pollTimer = window.setInterval(() => {
      void (async () => {
        try {
          await loadSnapshotForUser(user);
          if (active) {
            setSnapshotError("");
          }
        } catch (error) {
          if (!active) {
            return;
          }
          setSnapshotError(String(error instanceof Error ? error.message : error));
        }
      })();
    }, 45000);

    return () => {
      active = false;
      window.clearInterval(pollTimer);
    };
  }, [mode, parsedCycleId, parsedOwnerIds.error, parsedOwnerIds.value, rolloutAllowed, user]);

  useEffect(() => {
    if (!user || !isAdmin || mode !== "admin") {
      return;
    }
    void loadAdminResources(user);
  }, [isAdmin, mode, user]);

  useEffect(() => {
    if (!user || !isAdmin || mode !== "admin" || adminTab !== "ai") {
      return;
    }
    if (adminAiHealth && adminPdfHealth) {
      return;
    }
    void loadAdminHealth(user, false);
  }, [adminAiHealth, adminPdfHealth, adminTab, isAdmin, mode, user]);

  useEffect(() => {
    if (!user || mode === "atlas" || mode === "admin") {
      return;
    }
    void loadModeData(user, mode);
  }, [mode, parsedCycleId, user]);

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
  }, [mode, modeDataPending, parsedCycleId, user]);

  function handleSignOut(): void {
    void (async () => {
      try {
        await logoutSession();
      } catch {
        // Ignore logout transport errors and still clear local state.
      } finally {
        setUser(null);
        setSnapshotPayload(null);
        router.replace("/login?return_to=%2F");
      }
    })();
  }

  async function loadSnapshotForUser(activeUser: AuthUser): Promise<void> {
    if (!parsedCycleId || parsedOwnerIds.error) {
      return;
    }
    const payload = await readAtlasSnapshot({
      actor_username: activeUser.username,
      cycle_id: parsedCycleId,
      include_analysis: true,
      owner_ids: parsedOwnerIds.value,
    });
    setSnapshotPayload(payload);
  }

  async function refreshDashboardModeData(
    activeUser: AuthUser,
    activeMode: string,
  ): Promise<void> {
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
  }

  async function loadAdminCycles(activeUser: AuthUser): Promise<void> {
    setAdminCyclesPending(true);
    setAdminCycleError("");
    try {
      const cycles = await readCyclesQuery({
        actor_username: activeUser.username,
        kind: "cycles.all",
      });
      const sorted = [...cycles].sort((left, right) => right.id - left.id);
      setAdminCycles(sorted);
    } catch (error) {
      setAdminCycleError(String(error instanceof Error ? error.message : error));
      setAdminCycles([]);
    } finally {
      setAdminCyclesPending(false);
    }
  }

  async function loadAdminUsersAndTeams(activeUser: AuthUser): Promise<void> {
    setAdminDataPending(true);
    setAdminDataError("");
    try {
      const [usersPayload, teamsPayload] = await Promise.all([
        readBackendQuery({
          actor_username: activeUser.username,
          kind: "users.all",
        }),
        readBackendQuery({
          actor_username: activeUser.username,
          kind: "teams.all",
        }),
      ]);
      const users = ((usersPayload.users as AdminUserRead[]) || []).sort((a, b) =>
        String(a.username || "").localeCompare(String(b.username || "")),
      );
      const teams = ((teamsPayload.teams as AdminTeamRead[]) || []).sort((a, b) =>
        String(a.name || "").localeCompare(String(b.name || "")),
      );
      setAdminUsers(users);
      setAdminTeams(teams);
    } catch (error) {
      setAdminDataError(String(error instanceof Error ? error.message : error));
      setAdminUsers([]);
      setAdminTeams([]);
    } finally {
      setAdminDataPending(false);
    }
  }

  async function loadAdminResources(activeUser: AuthUser): Promise<void> {
    await Promise.all([loadAdminCycles(activeUser), loadAdminUsersAndTeams(activeUser)]);
  }

  async function loadAdminHealth(activeUser: AuthUser, liveProbe: boolean): Promise<void> {
    setAdminHealthPending(true);
    setAdminDataError("");
    try {
      const [aiHealth, pdfHealth] = await Promise.all([
        readAdminAiHealth({
          actor_username: activeUser.username,
          live_probe: liveProbe,
        }),
        readAdminPdfHealth({
          actor_username: activeUser.username,
        }),
      ]);
      setAdminAiHealth(aiHealth);
      setAdminPdfHealth(pdfHealth);
    } catch (error) {
      setAdminDataError(String(error instanceof Error ? error.message : error));
    } finally {
      setAdminHealthPending(false);
    }
  }

  async function handleAdminBackupExport(): Promise<void> {
    if (!user || !isAdmin) {
      return;
    }
    setAdminBackupPending(true);
    setAdminDataError("");
    try {
      const blob = await readAdminDbBackup({ actor_username: user.username });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      const stamp = new Date().toISOString().replace(/[:]/g, "-");
      anchor.href = url;
      anchor.download = `okr_backup_${stamp}.json`;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      URL.revokeObjectURL(url);
      setAdminCycleMessage("Backup downloaded.");
      setAdminBackupRestoreResult(null);
    } catch (error) {
      setAdminDataError(String(error instanceof Error ? error.message : error));
    } finally {
      setAdminBackupPending(false);
    }
  }

  async function handleAdminBackupRestore(): Promise<void> {
    if (!user || !isAdmin) {
      return;
    }
    if (!adminBackupFile) {
      setAdminDataError("Upload a backup JSON file first.");
      return;
    }
    if (adminBackupConfirm.trim() !== "RESTORE") {
      setAdminDataError('Type "RESTORE" to confirm.');
      return;
    }
    setAdminBackupPending(true);
    setAdminDataError("");
    try {
      const raw = await adminBackupFile.text();
      const payload = JSON.parse(raw) as Record<string, unknown>;
      const result = await restoreAdminDbBackup({
        actor_username: user.username,
        payload,
      });
      setAdminBackupRestoreResult(result);
      setAdminCycleMessage("Backup restored.");
      await loadAdminResources(user);
    } catch (error) {
      setAdminDataError(String(error instanceof Error ? error.message : error));
    } finally {
      setAdminBackupPending(false);
    }
  }

  async function handleAdminCreateUser(): Promise<void> {
    if (!user || !isAdmin) {
      return;
    }
    const username = adminUserDraft.username.trim();
    const password = adminUserDraft.password;
    if (!username || !password) {
      setAdminDataError("Username and password are required.");
      setAdminCycleMessage("");
      return;
    }
    try {
      const managerCandidate = Number.parseInt(adminUserDraft.managerId.trim(), 10);
      const teamCandidate = Number.parseInt(adminUserDraft.teamId.trim(), 10);
      await createUserMutation({
        actor_username: user.username,
        username,
        password,
        role: adminUserDraft.role,
        display_name: adminUserDraft.displayName.trim() || username,
        manager_id: Number.isFinite(managerCandidate) && managerCandidate > 0 ? managerCandidate : undefined,
        team_id: Number.isFinite(teamCandidate) && teamCandidate > 0 ? teamCandidate : undefined,
        must_change_password: adminUserDraft.mustChangePassword,
      });
      setAdminCycleMessage(`User "${username}" created.`);
      setAdminDataError("");
      setAdminUserDraft({
        username: "",
        displayName: "",
        password: "",
        role: "member",
        managerId: "",
        teamId: "",
        mustChangePassword: true,
      });
      await loadAdminUsersAndTeams(user);
    } catch (error) {
      setAdminDataError(String(error instanceof Error ? error.message : error));
    }
  }

  async function handleAdminToggleUserActive(userRow: AdminUserRead): Promise<void> {
    if (!user || !isAdmin) {
      return;
    }
    try {
      await updateUserMutation({
        actor_username: user.username,
        user_id: userRow.id,
        is_active: !userRow.is_active,
      });
      setAdminCycleMessage(
        `${userRow.username} ${userRow.is_active ? "deactivated" : "activated"}.`,
      );
      setAdminDataError("");
      await loadAdminUsersAndTeams(user);
    } catch (error) {
      setAdminDataError(String(error instanceof Error ? error.message : error));
    }
  }

  async function handleAdminCreateTeam(): Promise<void> {
    if (!user || !isAdmin) {
      return;
    }
    const teamName = adminTeamDraft.name.trim();
    if (!teamName) {
      setAdminDataError("Team name is required.");
      return;
    }
    try {
      await createTeamMutation({
        actor_username: user.username,
        name: teamName,
        description: adminTeamDraft.description.trim() || undefined,
      });
      setAdminCycleMessage(`Team "${teamName}" created.`);
      setAdminDataError("");
      setAdminTeamDraft({ name: "", description: "" });
      await loadAdminUsersAndTeams(user);
    } catch (error) {
      setAdminDataError(String(error instanceof Error ? error.message : error));
    }
  }

  async function handleAdminUpdateTeam(team: AdminTeamRead): Promise<void> {
    if (!user || !isAdmin) {
      return;
    }
    try {
      await updateTeamMutation({
        actor_username: user.username,
        team_id: team.id,
        name: team.name,
        description: team.description || undefined,
      });
      setAdminCycleMessage(`Team "${team.name}" updated.`);
      setAdminDataError("");
      await loadAdminUsersAndTeams(user);
    } catch (error) {
      setAdminDataError(String(error instanceof Error ? error.message : error));
    }
  }

  async function handleAdminDeleteTeam(team: AdminTeamRead): Promise<void> {
    if (!user || !isAdmin) {
      return;
    }
    if (typeof window !== "undefined") {
      const confirmed = window.confirm(`Delete team "${team.name}"?`);
      if (!confirmed) {
        return;
      }
    }
    try {
      await deleteTeamMutation({
        actor_username: user.username,
        team_id: team.id,
      });
      setAdminCycleMessage(`Team "${team.name}" deleted.`);
      setAdminDataError("");
      await loadAdminUsersAndTeams(user);
    } catch (error) {
      setAdminDataError(String(error instanceof Error ? error.message : error));
    }
  }

  async function handleAdminResetPassword(): Promise<void> {
    if (!user || !isAdmin) {
      return;
    }
    const userId = Number.parseInt(adminResetDraft.userId.trim(), 10);
    if (!Number.isFinite(userId) || userId <= 0 || !adminResetDraft.newPassword) {
      setAdminDataError("Valid user ID and new password are required.");
      return;
    }
    try {
      await resetUserPasswordMutation({
        actor_username: user.username,
        user_id: userId,
        new_password: adminResetDraft.newPassword,
        require_change: adminResetDraft.requireChange,
      });
      setAdminCycleMessage(`Password reset for user #${userId}.`);
      setAdminDataError("");
      setAdminResetDraft({ userId: "", newPassword: "", requireChange: false });
    } catch (error) {
      setAdminDataError(String(error instanceof Error ? error.message : error));
    }
  }

  async function handleAdminCreateCycle(): Promise<void> {
    if (!user || !isAdmin) {
      return;
    }
    const title = adminCreateCycleDraft.title.trim();
    if (!title || !adminCreateCycleDraft.startDate || !adminCreateCycleDraft.endDate) {
      setAdminCycleError("Title, start date, and end date are required.");
      setAdminCycleMessage("");
      return;
    }
    setAdminCycleError("");
    setAdminCycleMessage("");
    try {
      await createCycleMutation({
        actor_username: user.username,
        title,
        start_date: toIsoStart(adminCreateCycleDraft.startDate),
        end_date: toIsoEnd(adminCreateCycleDraft.endDate),
        is_active: adminCreateCycleDraft.isActive,
      });
      setAdminCycleMessage("Cycle created.");
      setAdminCreateCycleDraft({
        title: "",
        startDate: "",
        endDate: "",
        isActive: false,
      });
      await loadAdminCycles(user);
    } catch (error) {
      setAdminCycleError(String(error instanceof Error ? error.message : error));
    }
  }

  async function handleAdminSetCycleActive(cycle: CycleSummary, isActive: boolean): Promise<void> {
    if (!user || !isAdmin) {
      return;
    }
    setAdminCycleError("");
    setAdminCycleMessage("");
    try {
      await updateCycleMutation({
        actor_username: user.username,
        cycle_id: cycle.id,
        title: cycle.title,
        start_date: String(cycle.start_date || ""),
        end_date: String(cycle.end_date || ""),
        is_active: isActive,
      });
      setAdminCycleMessage(isActive ? "Cycle activated." : "Cycle deactivated.");
      await loadAdminCycles(user);
      if (isActive) {
        setResolvedCycle({
          id: cycle.id,
          title: cycle.title,
          start_date: cycle.start_date || null,
          end_date: cycle.end_date || null,
        });
        setCycleId(String(cycle.id));
      }
    } catch (error) {
      setAdminCycleError(String(error instanceof Error ? error.message : error));
    }
  }

  async function handleAdminDeleteCycle(cycle: CycleSummary): Promise<void> {
    if (!user || !isAdmin) {
      return;
    }
    if (typeof window !== "undefined") {
      const confirmed = window.confirm(`Delete cycle "${cycle.title}"? This cannot be undone.`);
      if (!confirmed) {
        return;
      }
    }
    setAdminCycleError("");
    setAdminCycleMessage("");
    try {
      await deleteCycleMutation({
        actor_username: user.username,
        cycle_id: cycle.id,
      });
      setAdminCycleMessage("Cycle deleted.");
      await loadAdminCycles(user);
    } catch (error) {
      setAdminCycleError(String(error instanceof Error ? error.message : error));
    }
  }

  async function loadModeData(activeUser: AuthUser, nextMode: string): Promise<void> {
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
          const [krPayload, weeklyPayload, retroPayload, logsPayload, experimentReviewPayload] =
            await Promise.all([
              readBackendQuery({
                actor_username: activeUser.username,
                kind: "krs.needing_checkin",
                params: {
                  user_id: activeUser.username,
                  cycle_id: parsedCycleId,
                  days_threshold: 7,
                },
              }),
              readBackendQuery({
                actor_username: activeUser.username,
                kind: "weekly_plan.active",
                params: { user_id: activeUser.id, date: new Date().toISOString() },
              }),
              readBackendQuery({
                actor_username: activeUser.username,
                kind: "retros.user",
                params: { user_id: activeUser.id, cycle_id: parsedCycleId },
              }),
              readBackendQuery({
                actor_username: activeUser.username,
                kind: "work_logs.by_range",
                params: {
                  user_id: activeUser.id,
                  start_date: review.start.toISOString(),
                  end_date: review.end.toISOString(),
                },
              }),
              readBackendQuery({
                actor_username: activeUser.username,
                kind: "experiments.for_retro_window",
                params: {
                  cycle_id: parsedCycleId,
                  window_start: review.start.toISOString(),
                  window_end: review.end.toISOString(),
                },
              }),
            ]);
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
  }

  async function loadLeadershipMetricsSnapshot(
    activeUser: AuthUser,
  ): Promise<LeadershipMetricsResponse | null> {
    if (!parsedCycleId) {
      setLeadershipMetrics(null);
      return null;
    }
    setLeadershipPending(true);
    setLeadershipError("");
    try {
      const metrics = await readLeadershipMetrics({
        actor_username: activeUser.username,
        cycle_id: parsedCycleId,
      });
      setLeadershipMetrics(metrics || null);
      return metrics || null;
    } catch (error) {
      setLeadershipError(String(error instanceof Error ? error.message : error));
      setLeadershipMetrics(null);
      return null;
    } finally {
      setLeadershipPending(false);
    }
  }

  async function handleGenerateTeamCoachSummary(): Promise<void> {
    if (!user || !parsedCycleId) {
      return;
    }
    const metrics = leadershipMetrics || (await loadLeadershipMetricsSnapshot(user)) || {};
    setTeamCoachPending(true);
    setTeamCoachError("");
    const baseline = buildTeamCoachBaseline(metrics);
    setTeamCoachSummary(baseline);
    try {
      const memberProgressData = Array.isArray(metrics.member_progress)
        ? metrics.member_progress
        : [];
      const memberDeadlineData = Array.isArray(metrics.member_deadlines)
        ? metrics.member_deadlines
        : [];
      const deadlineAggregate = memberDeadlineData.reduce<{
        completed: number;
        on_track: number;
        at_risk: number;
        overdue: number;
      }>(
        (acc, row) => {
          const item = (row || {}) as Record<string, unknown>;
          acc.completed += Number(item.completed || 0);
          acc.on_track += Number(item.on_track || 0);
          acc.at_risk += Number(item.at_risk || 0);
          acc.overdue += Number(item.overdue || 0);
          return acc;
        },
        { completed: 0, on_track: 0, at_risk: 0, overdue: 0 },
      );
      const teamData = {
        members: memberProgressData,
        total_with_deadline:
          deadlineAggregate.completed +
          deadlineAggregate.on_track +
          deadlineAggregate.at_risk +
          deadlineAggregate.overdue,
        completed: deadlineAggregate.completed,
        on_track: deadlineAggregate.on_track,
        at_risk: deadlineAggregate.at_risk,
        overdue: deadlineAggregate.overdue,
        total_krs: Number(metrics.total_krs || 0),
        at_risk_krs: Array.isArray(metrics.at_risk) ? metrics.at_risk.length : 0,
        avg_confidence: Number(metrics.avg_confidence || 0),
        hygiene_pct: Number(metrics.hygiene_pct || 0),
        progress_distribution: memberProgressData,
      };
      const aiPayload = await analyzeTeamCoachAi({
        actor_username: user.username,
        team_data: teamData,
      });
      const ai =
        parseTeamCoachFromCoachingPayload(aiPayload) || parseTeamCoachSummary(aiPayload);
      if (!ai.healthGrade && ai.healthScore === null && !ai.topPriorities.length) {
        throw new Error("AI team coach returned empty payload.");
      }
      setTeamCoachSummary({
        healthScore: ai.healthScore ?? baseline.healthScore,
        healthGrade: ai.healthGrade || baseline.healthGrade,
        topPriorities: ai.topPriorities.length ? ai.topPriorities : baseline.topPriorities,
        quickWins: ai.quickWins.length ? ai.quickWins : baseline.quickWins,
        watchOuts: ai.watchOuts.length ? ai.watchOuts : baseline.watchOuts,
        dimensionNotes: ai.dimensionNotes.length ? ai.dimensionNotes : baseline.dimensionNotes,
      });
    } catch (error) {
      setTeamCoachError(`${String(error instanceof Error ? error.message : error)} (showing baseline analysis).`);
    } finally {
      setTeamCoachPending(false);
    }
  }

  async function handleGenerateStrategyPulseSummary(): Promise<void> {
    if (!user || !parsedCycleId) {
      return;
    }
    const metrics = leadershipMetrics || (await loadLeadershipMetricsSnapshot(user)) || {};
    setStrategyPulsePending(true);
    setStrategyPulseError("");
    const baseline = buildStrategyPulseBaseline(metrics);
    setStrategyPulseSummary(baseline);
    try {
      const aiPayload = await readStrategyPulseAi({
        actor_username: user.username,
        cycle_id: parsedCycleId,
        cycle_title: cycleDisplayLabel(resolvedCycle),
      });
      const ai = parseStrategyPulseSummary(aiPayload || {});
      setStrategyPulseSummary({
        burnoutRisk: ai.burnoutRisk || baseline.burnoutRisk,
        burnoutScore: ai.burnoutScore ?? baseline.burnoutScore,
        avgDailyMinutes: ai.avgDailyMinutes ?? baseline.avgDailyMinutes,
        completedTasks14d: ai.completedTasks14d ?? baseline.completedTasks14d,
        gapSignals: ai.gapSignals.length ? ai.gapSignals : baseline.gapSignals,
        predictiveOutlook: ai.predictiveOutlook || baseline.predictiveOutlook,
        confidenceLevel: ai.confidenceLevel ?? baseline.confidenceLevel,
        mitigationSteps: ai.mitigationSteps.length ? ai.mitigationSteps : baseline.mitigationSteps,
        strategicPivots: ai.strategicPivots.length ? ai.strategicPivots : baseline.strategicPivots,
        portfolioActions: ai.portfolioActions.length ? ai.portfolioActions : baseline.portfolioActions,
      });
    } catch (error) {
      setStrategyPulseError(`${String(error instanceof Error ? error.message : error)} (showing baseline analysis).`);
    } finally {
      setStrategyPulsePending(false);
    }
  }

  function updateRitualCheckInDraft(krId: number, patch: Partial<CheckInDraft>): void {
    setRitualCheckInError((prev) => ({ ...prev, [krId]: "" }));
    setRitualCheckInMessage((prev) => ({ ...prev, [krId]: "" }));
    setRitualCheckInDrafts((prev) => {
      const base = prev[krId] || {
        value: "0",
        confidence: "7",
        comment: "",
        variationType: "COMMON_CAUSE" as const,
        specialCauseNote: "",
        experimentId: "",
      };
      return {
        ...prev,
        [krId]: {
          ...base,
          ...patch,
        },
      };
    });
  }

  function updateRitualExperimentDraft(krId: number, patch: Partial<ExperimentDraft>): void {
    setRitualExperimentDrafts((prev) => {
      const base = prev[krId] || {
        hypothesis: "",
        changeDescription: "",
        expectedEffectDirection: "",
        expectedEffectSize: "",
      };
      return {
        ...prev,
        [krId]: {
          ...base,
          ...patch,
        },
      };
    });
  }

  function updateRitualExperimentCloseDraft(
    experimentId: number,
    patch: Partial<ExperimentCloseDraft>,
  ): void {
    setRitualExperimentActionError((prev) => ({ ...prev, [experimentId]: "" }));
    setRitualExperimentActionMessage((prev) => ({ ...prev, [experimentId]: "" }));
    setRitualExperimentCloseDrafts((prev) => {
      const base = prev[experimentId] || {
        decision: "ITERATE" as ExperimentDecisionType,
        rationale: "",
      };
      return {
        ...prev,
        [experimentId]: {
          ...base,
          ...patch,
        },
      };
    });
  }

  async function handleRitualExperimentStart(experimentId: number): Promise<void> {
    if (!user) {
      return;
    }
    setRitualExperimentActionPending((prev) => ({ ...prev, [experimentId]: true }));
    setRitualExperimentActionError((prev) => ({ ...prev, [experimentId]: "" }));
    setRitualExperimentActionMessage((prev) => ({ ...prev, [experimentId]: "" }));
    try {
      await updateExperimentMutation({
        actor_username: user.username,
        experiment_id: experimentId,
        updates: {
          status: "RUNNING",
          start_at: new Date().toISOString(),
        },
      });
      setRitualExperimentActionMessage((prev) => ({
        ...prev,
        [experimentId]: "Experiment is now RUNNING.",
      }));
      await loadModeData(user, "ritual");
      if (parsedCycleId) {
        await loadSnapshotForUser(user);
      }
    } catch (error) {
      setRitualExperimentActionError((prev) => ({
        ...prev,
        [experimentId]: String(error instanceof Error ? error.message : error),
      }));
    } finally {
      setRitualExperimentActionPending((prev) => ({ ...prev, [experimentId]: false }));
    }
  }

  async function handleRitualExperimentClose(experimentId: number): Promise<void> {
    if (!user) {
      return;
    }
    const draft = ritualExperimentCloseDrafts[experimentId] || {
      decision: "ITERATE" as ExperimentDecisionType,
      rationale: "",
    };
    const rationale = String(draft.rationale || "").trim();
    if (!rationale) {
      setRitualExperimentActionError((prev) => ({
        ...prev,
        [experimentId]: "Decision rationale is required.",
      }));
      return;
    }
    setRitualExperimentActionPending((prev) => ({ ...prev, [experimentId]: true }));
    setRitualExperimentActionError((prev) => ({ ...prev, [experimentId]: "" }));
    setRitualExperimentActionMessage((prev) => ({ ...prev, [experimentId]: "" }));
    try {
      await closeExperimentMutation({
        actor_username: user.username,
        experiment_id: experimentId,
        decision: draft.decision,
        rationale,
      });
      setRitualExperimentActionMessage((prev) => ({
        ...prev,
        [experimentId]: `Experiment closed as ${draft.decision}.`,
      }));
      await loadModeData(user, "ritual");
      if (parsedCycleId) {
        await loadSnapshotForUser(user);
      }
    } catch (error) {
      setRitualExperimentActionError((prev) => ({
        ...prev,
        [experimentId]: String(error instanceof Error ? error.message : error),
      }));
    } finally {
      setRitualExperimentActionPending((prev) => ({ ...prev, [experimentId]: false }));
    }
  }

  async function handleRitualExperimentCreate(kr: KeyResultRead): Promise<void> {
    if (!user || !parsedCycleId) {
      return;
    }
    const krId = Number(kr.id);
    if (!Number.isFinite(krId) || krId <= 0) {
      return;
    }
    const draft = ritualExperimentDrafts[krId] || {
      hypothesis: "",
      changeDescription: "",
      expectedEffectDirection: "",
      expectedEffectSize: "",
    };
    const hypothesis = draft.hypothesis.trim();
    const changeDescription = draft.changeDescription.trim();
    if (!hypothesis || !changeDescription) {
      setRitualExperimentError((prev) => ({
        ...prev,
        [krId]: "Hypothesis and change description are required.",
      }));
      return;
    }
    const expectedEffectSizeText = draft.expectedEffectSize.trim();
    const expectedEffectSize = expectedEffectSizeText
      ? Number(expectedEffectSizeText)
      : undefined;
    if (
      expectedEffectSizeText &&
      (!Number.isFinite(expectedEffectSize) || Number.isNaN(expectedEffectSize))
    ) {
      setRitualExperimentError((prev) => ({
        ...prev,
        [krId]: "Expected effect size must be numeric.",
      }));
      return;
    }

    setRitualExperimentPending((prev) => ({ ...prev, [krId]: true }));
    setRitualExperimentError((prev) => ({ ...prev, [krId]: "" }));
    setRitualExperimentMessage((prev) => ({ ...prev, [krId]: "" }));
    try {
      const created: ExperimentMutationResponse = await createExperimentMutation({
        actor_username: user.username,
        key_result_id: krId,
        cycle_id: parsedCycleId,
        hypothesis,
        change_description: changeDescription,
        start_at: new Date().toISOString(),
        expected_effect_direction: draft.expectedEffectDirection || undefined,
        expected_effect_size: expectedEffectSize,
      });
      setRitualExperimentsByKr((prev) => {
        const existing = prev[krId] || [];
        const createdRow: ExperimentRead = {
          id: created.id,
          key_result_id: created.key_result_id,
          cycle_id: created.cycle_id,
          created_by: created.created_by,
          hypothesis: created.hypothesis,
          change_description: created.change_description,
          status: created.status,
          start_at: created.start_at,
          end_at: created.end_at,
          created_at: created.created_at,
          decision: created.decision,
          decision_rationale: created.decision_rationale,
          expected_effect_direction: created.expected_effect_direction,
          expected_effect_size: created.expected_effect_size,
        };
        return {
          ...prev,
          [krId]: [createdRow, ...existing],
        };
      });
      setRitualExperimentDrafts((prev) => ({
        ...prev,
        [krId]: {
          hypothesis: "",
          changeDescription: "",
          expectedEffectDirection: "",
          expectedEffectSize: "",
        },
      }));
      setRitualExperimentFormOpen((prev) => ({ ...prev, [krId]: false }));
      setRitualExperimentMessage((prev) => ({
        ...prev,
        [krId]: "Experiment created as PLANNED. Start it before linking to a check-in.",
      }));
    } catch (error) {
      setRitualExperimentError((prev) => ({
        ...prev,
        [krId]: String(error instanceof Error ? error.message : error),
      }));
    } finally {
      setRitualExperimentPending((prev) => ({ ...prev, [krId]: false }));
    }
  }

  async function handleRitualCheckInSubmit(kr: KeyResultRead): Promise<void> {
    if (!user) {
      return;
    }
    const krId = Number(kr.id);
    const draft = ritualCheckInDrafts[krId];
    if (!draft) {
      setRitualCheckInError((prev) => ({ ...prev, [krId]: "Check-in form is not initialized yet." }));
      return;
    }
    const value = Number(draft.value);
    const confidence = Number.parseInt(draft.confidence, 10);
    if (!Number.isFinite(value)) {
      setRitualCheckInError((prev) => ({ ...prev, [krId]: "Check-in value must be numeric." }));
      return;
    }
    if (!Number.isFinite(confidence) || confidence < 0 || confidence > 10) {
      setRitualCheckInError((prev) => ({ ...prev, [krId]: "Confidence must be between 0 and 10." }));
      return;
    }
    const comment = draft.comment.trim();
    if (confidence <= 5 && !comment) {
      setRitualCheckInError((prev) => ({
        ...prev,
        [krId]: "Low-confidence check-ins require a comment explaining risks and next action.",
      }));
      return;
    }
    const specialCauseNote = draft.specialCauseNote.trim();
    if (draft.variationType === "SPECIAL_CAUSE" && !specialCauseNote) {
      setRitualCheckInError((prev) => ({
        ...prev,
        [krId]: "Special cause check-ins require a special-cause note.",
      }));
      return;
    }
    const experimentIdCandidate = Number.parseInt(String(draft.experimentId || "").trim(), 10);
    const experimentId =
      draft.variationType === "COMMON_CAUSE" &&
      Number.isFinite(experimentIdCandidate) &&
      experimentIdCandidate > 0
        ? experimentIdCandidate
        : undefined;
    if (experimentId) {
      const linkedExperiment = (ritualExperimentsByKr[krId] || []).find((exp) => exp.id === experimentId);
      if (!linkedExperiment) {
        setRitualCheckInError((prev) => ({
          ...prev,
          [krId]: "Selected experiment is not available for this KR.",
        }));
        return;
      }
      if (String(linkedExperiment.status || "").toUpperCase() !== "RUNNING") {
        setRitualCheckInError((prev) => ({
          ...prev,
          [krId]: "Only RUNNING experiments can be linked to check-ins.",
        }));
        return;
      }
    }

    setRitualCheckInPending((prev) => ({ ...prev, [krId]: true }));
    setRitualCheckInError((prev) => ({ ...prev, [krId]: "" }));
    setRitualCheckInMessage((prev) => ({ ...prev, [krId]: "" }));
    try {
      await createCheckInMutation({
        actor_username: user.username,
        kr_id: krId,
        value,
        confidence,
        comment,
        variation_type: draft.variationType,
        special_cause_note: draft.variationType === "SPECIAL_CAUSE" ? specialCauseNote : "",
        experiment_id: experimentId,
      });
      setRitualCheckInMessage((prev) => ({ ...prev, [krId]: "Check-in saved." }));
      await loadModeData(user, "ritual");
      if (parsedCycleId) {
        await loadSnapshotForUser(user);
      }
    } catch (error) {
      setRitualCheckInError((prev) => ({
        ...prev,
        [krId]: String(error instanceof Error ? error.message : error),
      }));
    } finally {
      setRitualCheckInPending((prev) => ({ ...prev, [krId]: false }));
    }
  }

  async function handleInspectorRunAnalysis(): Promise<void> {
    if (!user || !selectedMeta || !rolloutAllowed) {
      return;
    }
    if (selectedMeta.type !== "KEY_RESULT" && selectedMeta.type !== "OBJECTIVE") {
      setInspectAnalysisError("AI analysis is available for Key Results and Objectives.");
      return;
    }
    setInspectAnalysisPending(true);
    setInspectAnalysisError("");
    setInspectMessage("");
    try {
      const analysisRaw = await analyzeNodeAi({
        actor_username: user.username,
        node_id: selectedMeta.id,
        node_type: selectedMeta.type === "KEY_RESULT" ? "KEY_RESULT" : "OBJECTIVE",
      });
      const analysis = parseAnalysisSummary(analysisRaw);
      setInspectAnalysis(analysis);
      await updateNodeMutation({
        actor_username: user.username,
        node_type: selectedMeta.type === "KEY_RESULT" ? "key_result" : "objective",
        node_id: selectedMeta.id,
        updates: {
          gemini_analysis: analysis.raw || analysisRaw,
        },
      });
      setInspectMessage(
        selectedMeta.type === "KEY_RESULT"
          ? `AI analysis refreshed for Key Result #${selectedMeta.id}.`
          : `AI analysis refreshed for Objective #${selectedMeta.id}.`,
      );
      if (parsedCycleId) {
        await loadSnapshotForUser(user);
      }
    } catch (error) {
      setInspectAnalysisError(String(error instanceof Error ? error.message : error));
    } finally {
      setInspectAnalysisPending(false);
    }
  }

  async function handleWeeklyPlanSave(refreshMode: "weekly" | "ritual" = "weekly"): Promise<void> {
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
  }

  async function handleRetroCreate(
    refreshMode: "retrobox" | "ritual" = "retrobox",
    weekStartIso?: string,
  ): Promise<void> {
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
  }

  async function waitForJobResult(activeUser: AuthUser, jobId: string, timeoutMs = 120_000): Promise<AsyncJobView> {
    const started = Date.now();
    while (Date.now() - started < timeoutMs) {
      const state = await readBackendJob({
        actor_username: activeUser.username,
        job_id: jobId,
      });
      const status = String(state.status || "").toLowerCase();
      if (status === "succeeded" || status === "failed" || status === "cancelled") {
        return state;
      }
      await new Promise((resolve) => window.setTimeout(resolve, 1000));
    }
    throw new Error("Timed out waiting for export job.");
  }

  function triggerDownloadFromBlob(blob: Blob, filename: string): void {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
  }

  function buildSimpleReportHtml(logs: WorkLogRead[], title: string): string {
    const rows = logs
      .map((log) => {
        const task = String(log.task?.title || `Task #${log.task_id || "-"}`);
        const duration = Math.round(Number(log.duration_minutes || 0));
        const started = String(formatOptionalDate(log.start_time));
        const summary = String(log.summary || "-");
        return `<tr><td>${task}</td><td>${duration}</td><td>${started}</td><td>${summary}</td></tr>`;
      })
      .join("");
    return `<!doctype html><html><head><meta charset="utf-8"><title>${title}</title></head><body><h2>${title}</h2><table border="1" cellspacing="0" cellpadding="6"><thead><tr><th>Task</th><th>Minutes</th><th>Start</th><th>Summary</th></tr></thead><tbody>${rows}</tbody></table></body></html>`;
  }

  async function handleReportExport(format: "pdf" | "html"): Promise<void> {
    if (!user) {
      return;
    }
    setReportExportPending(true);
    setReportExportError("");
    try {
      const now = new Date();
      const start = new Date(now);
      if (mode === "daily") {
        start.setHours(0, 0, 0, 0);
      } else {
        start.setDate(start.getDate() - 6);
        start.setHours(0, 0, 0, 0);
      }
      const end = new Date(now);
      end.setHours(23, 59, 59, 999);
      const logPayload = await readBackendQuery({
        actor_username: user.username,
        kind: "work_logs.by_range",
        params: {
          user_id: user.id,
          start_date: start.toISOString(),
          end_date: end.toISOString(),
        },
      });
      const logs = ((logPayload.work_logs as WorkLogRead[]) || []).slice(0, 500);
      const reportItems = logs.map((log) => ({
        Task: String(log.task?.title || `Task #${log.task_id || "-"}`),
        "Duration (m)": Math.round(Number(log.duration_minutes || 0)),
        Date: String(log.start_time || ""),
        Time: String(log.start_time || ""),
        Summary: String(log.summary || ""),
        Objective: "-",
        KeyResult: "-",
      }));
      const objectiveStats: Record<string, number> = {};
      const totalTime = `${Math.round(logs.reduce((sum, row) => sum + Number(row.duration_minutes || 0), 0))} min`;
      const fileStamp = new Date().toISOString().slice(0, 10);
      if (format === "html") {
        const html = buildSimpleReportHtml(
          logs,
          mode === "daily" ? "Daily Work Report" : "Weekly Work Report",
        );
        triggerDownloadFromBlob(new Blob([html], { type: "text/html" }), `${mode}_report_${fileStamp}.html`);
        return;
      }

      const submitted = await submitBackendJob({
        actor_username: user.username,
        kind: "pdf.weekly",
        payload: {
          report_items: reportItems,
          objective_stats: objectiveStats,
          total_time_str: totalTime,
          key_results: [],
          direction: "LTR",
          title: mode === "daily" ? "Daily Work Report" : "Weekly Work Report",
          time_label: mode === "daily" ? "Today" : "Last 7 Days",
          report_summary: "",
          achievements: [],
        },
      });
      const done = await waitForJobResult(user, submitted.id);
      const resultPayload = done.result || {};
      const encoded = String((resultPayload as Record<string, unknown>).content_b64 || "");
      if (!encoded) {
        const fallbackHtml = buildSimpleReportHtml(
          logs,
          mode === "daily" ? "Daily Work Report" : "Weekly Work Report",
        );
        triggerDownloadFromBlob(new Blob([fallbackHtml], { type: "text/html" }), `${mode}_report_${fileStamp}.html`);
        setReportExportError(String(done.error_text || "PDF export unavailable; downloaded HTML fallback."));
        return;
      }
      const binary = atob(encoded);
      const bytes = new Uint8Array(binary.length);
      for (let idx = 0; idx < binary.length; idx += 1) {
        bytes[idx] = binary.charCodeAt(idx);
      }
      triggerDownloadFromBlob(new Blob([bytes], { type: "application/pdf" }), `${mode}_report_${fileStamp}.pdf`);
    } catch (error) {
      setReportExportError(String(error instanceof Error ? error.message : error));
    } finally {
      setReportExportPending(false);
    }
  }

  async function handleReportAiSummaryGenerate(): Promise<void> {
    if (!user) {
      return;
    }
    setReportAiPending(true);
    setReportAiError("");
    setReportAiSummary(null);
    try {
      const now = new Date();
      const start = new Date(now);
      if (mode === "daily") {
        start.setHours(0, 0, 0, 0);
      } else {
        start.setDate(start.getDate() - 6);
        start.setHours(0, 0, 0, 0);
      }
      const end = new Date(now);
      end.setHours(23, 59, 59, 999);
      const logPayload = await readBackendQuery({
        actor_username: user.username,
        kind: "work_logs.by_range",
        params: {
          user_id: user.id,
          start_date: start.toISOString(),
          end_date: end.toISOString(),
        },
      });
      const logs = ((logPayload.work_logs as WorkLogRead[]) || []).slice(0, 300);
      const normalizedLogs = logs.map((log) => ({
        task: String(log.task?.title || `Task #${log.task_id || "-"}`),
        duration_minutes: Math.round(Number(log.duration_minutes || 0)),
        start_time: log.start_time || null,
        summary: String(log.summary || "").trim(),
      }));
      const totalMinutes = Math.round(
        normalizedLogs.reduce((sum, row) => sum + Number(row.duration_minutes || 0), 0),
      );
      const prompt = [
        "Return strict JSON only with keys: summary_markdown, highlights, focus_analysis.",
        "summary_markdown should be a concise executive summary in markdown.",
        "highlights should be an array of 3-7 short bullet points.",
        "focus_analysis should be one sentence about strategic vs tactical focus.",
        `report_mode=${mode}`,
        `window_start=${start.toISOString()}`,
        `window_end=${end.toISOString()}`,
        `total_minutes=${totalMinutes}`,
        `logs=${JSON.stringify(normalizedLogs)}`,
      ].join("\n");
      const submitted = await submitBackendJob({
        actor_username: user.username,
        kind: "ai.generate_json",
        payload: { prompt },
      });
      const done = await waitForJobResult(user, submitted.id);
      if (String(done.status || "").toLowerCase() !== "succeeded") {
        throw new Error(String(done.error_text || "AI report summary generation failed."));
      }
      const summary = parseReportAiSummary(done.result || {});
      if (!summary.summaryMarkdown && !summary.highlights.length && !summary.focusAnalysis) {
        throw new Error("AI response did not contain a usable report summary payload.");
      }
      setReportAiSummary(summary);
    } catch (error) {
      setReportAiError(String(error instanceof Error ? error.message : error));
    } finally {
      setReportAiPending(false);
    }
  }

  async function handleAiProgressSync(previewOnly: boolean): Promise<void> {
    if (!user || !atlasRuntime || !rolloutAllowed) {
      return;
    }
    const maxDelta = AI_SYNC_MAX_DELTA;
    setAiSyncPending(true);
    setAiSyncError("");
    setAiSyncMessage("");
    setAiSuggestion(null);
    try {
      const krRefs = allScopeRefs.filter((ref) => atlasRuntime.index[ref]?.type === "KEY_RESULT");
      let analyzed = 0;
      let applied = 0;
      let planned = 0;
      let missingAiScore = 0;
      let skippedDeltaCap = 0;
      let skippedDecrease = 0;
      let unchanged = 0;
      const failed: string[] = [];
      const undoItems: AiProgressUndoItem[] = [];

      for (const ref of krRefs) {
        const meta = atlasRuntime.index[ref];
        if (!meta || meta.type !== "KEY_RESULT") {
          continue;
        }
        analyzed += 1;
        const krNode = meta.node as AtlasKeyResultSnapshot;
        const decision = aiProgressDecision(
          meta.progress,
          krNode.ai_overall_score,
          maxDelta,
          AI_SYNC_ALLOW_DECREASE,
        );
        if (decision.action !== "apply") {
          if (decision.reason === "missing_ai_score") {
            missingAiScore += 1;
          } else if (decision.reason === "delta_cap") {
            skippedDeltaCap += 1;
          } else if (decision.reason === "decrease_blocked") {
            skippedDecrease += 1;
          } else if (decision.reason === "no_change") {
            unchanged += 1;
          }
          continue;
        }
        if (previewOnly) {
          planned += 1;
          continue;
        }
        try {
          await updateNodeMutation({
            actor_username: user.username,
            node_type: "key_result",
            node_id: meta.id,
            updates: {
              progress: decision.proposed,
            },
          });
          undoItems.push({
            krId: meta.id,
            title: meta.title,
            previousProgress: decision.current,
            newProgress: decision.proposed || 0,
          });
          applied += 1;
        } catch (error) {
          failed.push(`${meta.title}: ${String(error instanceof Error ? error.message : error)}`);
        }
      }

      setAiSyncReport({
        total: krRefs.length,
        analyzed,
        applied,
        planned,
        missingAiScore,
        skippedDeltaCap,
        skippedDecrease,
        unchanged,
        failed: failed.slice(0, 8),
      });

      if (!previewOnly && undoItems.length > 0) {
        setAiProgressUndoItems(undoItems);
      }

      if (previewOnly) {
        setAiSyncMessage(`Preview complete: ${planned} KR changes planned (${analyzed}/${krRefs.length} analyzed).`);
      } else {
        setAiSyncMessage(`AI sync complete: ${applied} KR updates applied (${analyzed}/${krRefs.length} analyzed).`);
      }

      if (!previewOnly && parsedCycleId) {
        await loadSnapshotForUser(user);
      }
    } catch (error) {
      setAiSyncError(String(error instanceof Error ? error.message : error));
    } finally {
      setAiSyncPending(false);
    }
  }

  async function handleAiProgressUndo(): Promise<void> {
    if (!user || !rolloutAllowed) {
      return;
    }
    if (!aiProgressUndoItems.length) {
      setAiSyncError("No AI progress sync changes available to undo.");
      setAiSyncMessage("");
      return;
    }
    setAiSyncPending(true);
    setAiSyncError("");
    setAiSyncMessage("");
    try {
      let restored = 0;
      const failed: string[] = [];
      for (const item of aiProgressUndoItems) {
        try {
          await updateNodeMutation({
            actor_username: user.username,
            node_type: "key_result",
            node_id: item.krId,
            updates: {
              progress: item.previousProgress,
            },
          });
          restored += 1;
        } catch (error) {
          failed.push(`${item.title}: ${String(error instanceof Error ? error.message : error)}`);
        }
      }
      setAiProgressUndoItems([]);
      setAiSyncReport((prev) =>
        prev
          ? {
              ...prev,
              failed: [...prev.failed, ...failed].slice(0, 8),
            }
          : null,
      );
      setAiSyncMessage(`Undo complete: restored ${restored} KR progress values.`);
      if (parsedCycleId) {
        await loadSnapshotForUser(user);
      }
    } catch (error) {
      setAiSyncError(String(error instanceof Error ? error.message : error));
    } finally {
      setAiSyncPending(false);
    }
  }

  async function handleAiSuggestNextTask(): Promise<void> {
    if (!user || !atlasRuntime || !rolloutAllowed) {
      return;
    }
    const candidates = taskRefs
      .map((ref) => {
        const taskMeta = atlasRuntime.index[ref];
        if (!taskMeta || taskMeta.type !== "TASK") {
          return null;
        }
        const parentKr = taskMeta.parent ? atlasRuntime.index[taskMeta.parent] : null;
        const parentKrScore =
          parentKr && parentKr.type === "KEY_RESULT"
            ? clampProgress((parentKr.node as AtlasKeyResultSnapshot).ai_overall_score)
            : null;
        const task = taskMeta.node as AtlasTaskSnapshot;
        const deadlineTs = task.deadline ? new Date(task.deadline).getTime() : Number.POSITIVE_INFINITY;
        const urgencyBonus = Number.isFinite(deadlineTs)
          ? Math.max(0, Math.round((Date.now() - deadlineTs) / (1000 * 60 * 60 * 24)))
          : 0;
        const priorityScore = (100 - clampProgress(taskMeta.progress)) + urgencyBonus + (parentKrScore ? (100 - parentKrScore) / 4 : 0);
        return {
          task_ref: ref,
          title: taskMeta.title,
          progress: clampProgress(taskMeta.progress),
          status: String(task.status || "IN_PROGRESS"),
          deadline: task.deadline || null,
          path: taskMeta.path.map((pathRef) => atlasRuntime.index[pathRef]?.title || pathRef).join(" > "),
          priority_score: Number(priorityScore.toFixed(2)),
        };
      })
      .filter((row): row is NonNullable<typeof row> => Boolean(row))
      .sort((a, b) => b.priority_score - a.priority_score)
      .slice(0, 40);

    if (!candidates.length) {
      setAiSyncError("No task candidates available in current Atlas scope.");
      setAiSuggestion(null);
      return;
    }

    setAiSuggestPending(true);
    setAiSyncError("");
    setAiSyncMessage("");
    setAiSuggestion(null);
    try {
      const prompt = [
        "Pick exactly one task_ref from the candidate list.",
        "Return strict JSON only with keys: task_ref, reason, confidence.",
        "confidence must be an integer from 0 to 100.",
        "Prefer highest urgency and impact.",
        `Candidates: ${JSON.stringify(candidates)}`,
      ].join("\n");
      const submitted = await submitBackendJob({
        actor_username: user.username,
        kind: "ai.generate_json",
        payload: { prompt },
      });
      const done = await waitForJobResult(user, submitted.id);
      if (String(done.status || "").toLowerCase() !== "succeeded") {
        throw new Error(String(done.error_text || "AI suggestion failed."));
      }
      const result = (done.result || {}) as Record<string, unknown>;
      const pickedRef = String(result.task_ref || "").trim();
      if (!pickedRef || !taskRefs.includes(pickedRef) || !atlasRuntime.index[pickedRef]) {
        throw new Error("AI returned an invalid task_ref outside current scope.");
      }
      const reason = String(result.reason || "").trim();
      const confidenceRaw = Number(result.confidence);
      const confidence = Number.isFinite(confidenceRaw) ? clampProgress(confidenceRaw) : null;
      setFocusTaskRef(pickedRef);
      setSelectedRef(pickedRef);
      setAiSuggestion({
        taskRef: pickedRef,
        reason,
        confidence,
      });
      setAiSyncMessage(`Suggested next task: ${atlasRuntime.index[pickedRef]?.title || pickedRef}`);
    } catch (error) {
      setAiSyncError(String(error instanceof Error ? error.message : error));
    } finally {
      setAiSuggestPending(false);
    }
  }

  async function loadMindmap(
    activeUser: AuthUser,
    nodeId: number,
    nodeType: AtlasIndexNode["type"],
  ): Promise<void> {
    setMindmapPending(true);
    setMindmapError("");
    try {
      const payload = await readBackendQuery({
        actor_username: activeUser.username,
        kind: "mindmap.root",
        params: { node_id: nodeId, node_type: nodeType },
      });
      setMindmapPayload((payload as Record<string, unknown>) || null);
    } catch (error) {
      setMindmapError(String(error instanceof Error ? error.message : error));
      setMindmapPayload(null);
    } finally {
      setMindmapPending(false);
    }
  }

  async function handleTimerStart(): Promise<void> {
    if (!user || !focusTaskMeta || !rolloutAllowed) {
      return;
    }
    setTimerPending(true);
    setTimerError("");
    setTimerMessage("");
    try {
      const response = await startTaskTimer({
        actor_username: user.username,
        task_id: focusTaskMeta.id,
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
  }

  async function handleTimerStop(): Promise<void> {
    if (!user || !rolloutAllowed) {
      return;
    }
    const resolvedTaskId = timerSessionTaskId || focusTaskMeta?.id || null;
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
  }

  async function handleInspectorSave(): Promise<void> {
    if (!user || !selectedMeta || !rolloutAllowed) {
      return;
    }
    const parsedProgress = Number.parseInt(inspectDraft.progress, 10);
    if (!Number.isFinite(parsedProgress) || parsedProgress < 0 || parsedProgress > 100) {
      setInspectError("Progress must be an integer between 0 and 100.");
      setInspectMessage("");
      return;
    }

    setInspectPending(true);
    setInspectError("");
    setInspectMessage("");
    try {
      await updateNodeMutation({
        actor_username: user.username,
        node_type: nodeTypeToPath(selectedMeta.type),
        node_id: selectedMeta.id,
        updates: {
          title: inspectDraft.title.trim(),
          description: inspectDraft.description.trim(),
          progress: parsedProgress,
        },
      });
      setInspectMessage(`Saved changes for ${nodeTypeLabel(selectedMeta.type)} #${selectedMeta.id}.`);
      if (parsedCycleId) {
        await loadSnapshotForUser(user);
      }
    } catch (error) {
      setInspectError(String(error instanceof Error ? error.message : error));
    } finally {
      setInspectPending(false);
    }
  }

  async function handleNodeCreate(): Promise<void> {
    if (!user || !rolloutAllowed) {
      return;
    }
    const title = createDraft.title.trim();
    if (!title) {
      setCreateError("Title is required for node creation.");
      setCreateMessage("");
      return;
    }
    if (!canCreateForContext) {
      setCreateError("Select a valid parent context before creating this node type.");
      setCreateMessage("");
      return;
    }

    const description = createDraft.description.trim();
    let payload: Record<string, unknown> = {
      title,
      description,
    };

    if (createDraft.createType === "goal") {
      payload = {
        user_id: user.username,
        title,
        description,
      };

      if (parsedCycleId) {
        payload.cycle_id = parsedCycleId;
      }

      const strategyTags = createDraft.tags
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean);
      if (strategyTags.length > 0) {
        payload.strategy_tags = strategyTags;
      }
    } else if (createDraft.createType === "objective") {
      payload.goal_id = createContext.goalId;
    } else if (createDraft.createType === "key_result") {
      const targetValue = Number.parseFloat(createDraft.targetValue.trim());
      if (!Number.isFinite(targetValue)) {
        setCreateError("Target value must be a valid number.");
        setCreateMessage("");
        return;
      }

      payload.objective_id = createContext.objectiveId;
      payload.target_value = targetValue;
      payload.unit = createDraft.unit.trim() || "%";

      const initiativeTags = createDraft.tags
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean);
      if (initiativeTags.length > 0) {
        payload.initiative_tags = initiativeTags;
      }
    } else {
      const estimatedMinutes = Number.parseInt(createDraft.estimatedMinutes.trim(), 10);
      if (!Number.isFinite(estimatedMinutes) || estimatedMinutes < 0) {
        setCreateError("Estimated minutes must be a non-negative integer.");
        setCreateMessage("");
        return;
      }
      payload.key_result_id = createContext.keyResultId;
      payload.estimated_minutes = estimatedMinutes;

      const assigneeCandidate = createDraft.assigneeId.trim();
      if (assigneeCandidate) {
        const assigneeId = Number.parseInt(assigneeCandidate, 10);
        if (!Number.isFinite(assigneeId) || assigneeId <= 0) {
          setCreateError("Assignee ID must be a positive integer.");
          setCreateMessage("");
          return;
        }
        payload.assignee_id = assigneeId;
      }
    }

    setCreatePending(true);
    setCreateError("");
    setCreateMessage("");
    setDeleteMessage("");
    try {
      const created = await createNodeMutation({
        actor_username: user.username,
        create_type: createDraft.createType,
        payload,
      });
      setCreateMessage(`Created ${nodeTypeLabel(created.node_type as AtlasIndexNode["type"])} #${created.id}.`);
      setCreateDraft((prev) => ({
        ...prev,
        title: "",
        description: "",
      }));
      if (parsedCycleId) {
        await loadSnapshotForUser(user);
      }
      setSelectedRef(mutationNodeRef(created.node_type as AtlasIndexNode["type"], created.id));
    } catch (error) {
      setCreateError(String(error instanceof Error ? error.message : error));
    } finally {
      setCreatePending(false);
    }
  }

  async function handleNodeDelete(): Promise<void> {
    if (!user || !selectedMeta || !rolloutAllowed) {
      return;
    }
    if (typeof window !== "undefined") {
      const confirmed = window.confirm(
        `Delete ${nodeTypeLabel(selectedMeta.type)} #${selectedMeta.id}? This cannot be undone.`,
      );
      if (!confirmed) {
        return;
      }
    }

    setDeletePending(true);
    setDeleteError("");
    setDeleteMessage("");
    setCreateMessage("");
    try {
      await deleteNodeMutation({
        actor_username: user.username,
        node_type: nodeTypeToPath(selectedMeta.type),
        node_id: selectedMeta.id,
      });
      setDeleteMessage(`Deleted ${nodeTypeLabel(selectedMeta.type)} #${selectedMeta.id}.`);
      setSelectedRef("");
      if (focusTaskRef === selectedMeta.ref) {
        setFocusTaskRef("");
      }
      if (parsedCycleId) {
        await loadSnapshotForUser(user);
      }
    } catch (error) {
      setDeleteError(String(error instanceof Error ? error.message : error));
    } finally {
      setDeletePending(false);
    }
  }

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
                disabled={!user || !focusTaskMeta || !rolloutAllowed}
                style={{ width: "100%" }}
              >
                Open timer modal
              </button>
            ) : (
              <button
                className="primary-button"
                type="button"
                onClick={handleTimerStart}
                disabled={timerPending || !user || !focusTaskMeta || !rolloutAllowed}
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
            <div style={{ marginTop: "0.16rem", fontSize: "0.8rem", color: "var(--ink-soft)" }}>
              @{user.username} - {user.role}
            </div>
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
        cycleId={cycleId}
        onCycleIdChange={setCycleId}
        ownerIdsInput={ownerIdsInput}
        onOwnerIdsInputChange={setOwnerIdsInput}
        mode={mode}
        onModeChange={handleSidebarModeSelect}
        sidebarItems={sidebarItems}
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
          onSelectRef={setSelectedRef}
          nodeQuery={nodeQuery}
          onNodeQueryChange={setNodeQuery}
          hasSnapshotPayload={Boolean(snapshotPayload)}
          nodeTagForType={(type) => TYPE_TAG[type as keyof typeof TYPE_TAG] || "N"}
        />

        <div className="atlas-inspector-pane">
          <p className="kicker">Inspector</p>
          <h2 style={{ margin: "0.1rem 0 0.4rem", fontSize: "1.05rem" }}>
            {selectedMeta
              ? selectedInspectorTitle
              : "Select a node"}
          </h2>

          <InspectorAiAssistPanel
            aiSyncMaxDelta={AI_SYNC_MAX_DELTA}
            aiSyncPending={aiSyncPending}
            aiSuggestPending={aiSuggestPending}
            hasUser={Boolean(user)}
            hasAtlasRuntime={Boolean(atlasRuntime)}
            rolloutAllowed={rolloutAllowed}
            hasAiUndoItems={aiProgressUndoItems.length > 0}
            hasTaskRefs={taskRefs.length > 0}
            aiSyncReport={aiSyncReport}
            aiSuggestion={aiSuggestion}
            aiSyncError={aiSyncError}
            aiSyncMessage={aiSyncMessage}
            onPreviewAiSync={() => {
              void handleAiProgressSync(true);
            }}
            onApplyAiSync={() => {
              void handleAiProgressSync(false);
            }}
            onUndoAiSync={() => {
              void handleAiProgressUndo();
            }}
            onSuggestNextTask={() => {
              void handleAiSuggestNextTask();
            }}
          />

          {selectedMeta && atlasRuntime ? (
            <>
              <p style={{ margin: 0, color: "var(--ink-soft)", minHeight: "2.5rem" }}>
                {selectedMeta.description || "No description."}
              </p>

              <div className="atlas-progress-wrap" style={{ marginTop: "0.75rem" }}>
                <div className="atlas-progress-track">
                  <div
                    className="atlas-progress-fill"
                    style={{ width: `${Math.max(0, Math.min(100, selectedMeta.progress))}%` }}
                  />
                </div>
                <span className="atlas-progress-label">Progress {selectedMeta.progress}%</span>
              </div>

              <p style={{ margin: "0.55rem 0 0", fontSize: "0.84rem", color: "var(--ink-soft)" }}>
                Owner: {selectedMeta.ownerName}
              </p>
              <p style={{ margin: "0.2rem 0 0", fontSize: "0.82rem", color: "var(--ink-soft)" }}>
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
                rolloutAllowed={rolloutAllowed}
                onNodeDelete={handleNodeDelete}
                deletePending={deletePending}
                selectedTypeLabel={nodeTypeLabel(selectedMeta.type)}
                inspectError={inspectError}
                inspectMessage={inspectMessage}
                showAiAnalysis={selectedMeta.type === "KEY_RESULT" || selectedMeta.type === "OBJECTIVE"}
                aiAnalysisTargetLabel={selectedMeta.type === "KEY_RESULT" ? "key result" : "objective"}
                onRunAnalysis={() => {
                  void handleInspectorRunAnalysis();
                }}
                inspectAnalysisPending={inspectAnalysisPending}
                inspectAnalysisError={inspectAnalysisError}
                inspectAnalysis={inspectAnalysis}
              />

              <InspectorManageNodesPanel
                createDraft={createDraft}
                onCreateDraftChange={(patch) => {
                  setCreateDraft((prev) => ({ ...prev, ...patch }));
                }}
                createContext={createContext}
                canCreateForContext={canCreateForContext}
                createTypeLabel={createTypeLabel}
                cycleLabel={cycleDisplayLabel(resolvedCycle)}
                onCreateNode={handleNodeCreate}
                createPending={createPending}
                hasUser={Boolean(user)}
                rolloutAllowed={rolloutAllowed}
                createError={createError}
                createMessage={createMessage}
                deleteError={deleteError}
                deleteMessage={deleteMessage}
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
                  rolloutAllowed={rolloutAllowed}
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

            </>
          ) : (
            <p style={{ margin: 0, color: "var(--ink-soft)" }}>
              Choose a Goal/Objective/KR/Task from Focus Map to inspect and edit details.
            </p>
          )}
        </div>
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
        adminAiHealth={adminAiHealth}
        adminPdfHealth={adminPdfHealth}
        adminCyclesPending={adminCyclesPending}
        adminDataPending={adminDataPending}
        adminCycleError={adminCycleError}
        adminDataError={adminDataError}
        adminCycleMessage={adminCycleMessage}
        adminCycles={adminCycles}
        onAdminSetCycleActive={handleAdminSetCycleActive}
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
            onOpenTaskInAtlas={(taskId) => {
              const ref = `task_${taskId}`;
              const routePath = pathForMode("atlas");
              const query = buildDeepLinkQuery({
                cycle: cycleId,
                mode: "atlas",
                sel: ref,
                ft: ref,
                lens,
              });
              router.replace(query ? `${routePath}?${query}` : routePath);
              setSelectedRef(ref);
              setFocusTaskRef(ref);
              setMode("atlas");
            }}
          />
        ) : null}
      </section>
      )}
        </div>
      </div>
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
                disabled={timerPending || !user || !rolloutAllowed}
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
