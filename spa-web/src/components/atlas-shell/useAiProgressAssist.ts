"use client";

import { useCallback, useEffect, useState } from "react";

import {
  submitBackendJob,
  updateNodeMutation,
  type AuthUser,
} from "@/lib/api";
import {
  clampProgress,
  aiProgressDecision,
} from "@/components/atlas-shell/shellAnalyticsUtils";
import { waitForBackendJobResult } from "@/components/atlas-shell/jobPolling";
import type {
  AtlasIndexNode,
  AtlasKeyResultSnapshot,
  AtlasTaskSnapshot,
} from "@/lib/atlas";

type AtlasRuntimeLike = {
  index: Record<string, AtlasIndexNode>;
};

export type AiProgressUndoItem = {
  krId: number;
  title: string;
  previousProgress: number;
  newProgress: number;
};

export type AiSyncReport = {
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

export type AiTaskSuggestion = {
  taskRef: string;
  reason: string;
  confidence: number | null;
};

type UseAiProgressAssistInput = {
  user: AuthUser | null;
  parsedCycleId: number | null;
  atlasRuntime: AtlasRuntimeLike | null;
  allScopeRefs: string[];
  taskRefs: string[];
  aiSyncMaxDelta: number;
  aiSyncAllowDecrease: boolean;
  loadSnapshotForUser: (activeUser: AuthUser) => Promise<void>;
  onTaskSuggested: (taskRef: string) => void;
};

export default function useAiProgressAssist({
  user,
  parsedCycleId,
  atlasRuntime,
  allScopeRefs,
  taskRefs,
  aiSyncMaxDelta,
  aiSyncAllowDecrease,
  loadSnapshotForUser,
  onTaskSuggested,
}: UseAiProgressAssistInput) {
  const [aiSyncPending, setAiSyncPending] = useState(false);
  const [aiSyncError, setAiSyncError] = useState("");
  const [aiSyncMessage, setAiSyncMessage] = useState("");
  const [aiSyncReport, setAiSyncReport] = useState<AiSyncReport | null>(null);
  const [aiProgressUndoItems, setAiProgressUndoItems] = useState<AiProgressUndoItem[]>([]);
  const [aiSuggestPending, setAiSuggestPending] = useState(false);
  const [aiSuggestion, setAiSuggestion] = useState<AiTaskSuggestion | null>(null);

  useEffect(() => {
    setAiSyncReport(null);
    setAiProgressUndoItems([]);
    setAiSuggestion(null);
    setAiSyncError("");
    setAiSyncMessage("");
  }, [parsedCycleId]);

  const handleAiProgressSync = useCallback(async (previewOnly: boolean): Promise<void> => {
    if (!user || !atlasRuntime) {
      return;
    }
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
          aiSyncMaxDelta,
          aiSyncAllowDecrease,
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
        if (planned > 0) {
          setAiSyncMessage(`Preview: ${planned} KR update${planned !== 1 ? "s" : ""} ready to apply. Click "Apply AI Sync" to confirm.`);
        } else {
          setAiSyncMessage(`Preview: no KR changes recommended. ${unchanged} unchanged, ${missingAiScore} without AI score.`);
        }
      } else {
        if (applied > 0) {
          setAiSyncMessage(`Applied ${applied} KR update${applied !== 1 ? "s" : ""}.`);
        } else {
          setAiSyncMessage(`No KR updates applied. ${unchanged} unchanged, ${skippedDecrease} decreases skipped.`);
        }
      }

      if (!previewOnly && parsedCycleId) {
        await loadSnapshotForUser(user);
      }
    } catch (error) {
      setAiSyncError(String(error instanceof Error ? error.message : error));
    } finally {
      setAiSyncPending(false);
    }
  }, [
    aiSyncAllowDecrease,
    aiSyncMaxDelta,
    allScopeRefs,
    atlasRuntime,
    loadSnapshotForUser,
    parsedCycleId,
    user,
  ]);

  const handleAiProgressUndo = useCallback(async (): Promise<void> => {
    if (!user) {
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
  }, [aiProgressUndoItems, loadSnapshotForUser, parsedCycleId, user]);

  const handleAiSuggestNextTask = useCallback(async (): Promise<void> => {
    if (!user || !atlasRuntime) {
      return;
    }
    // Capture refs at call time to avoid race with snapshot refresh.
    const snapshotRefs = [...taskRefs];
    const snapshotIndex = { ...atlasRuntime.index };
    const candidates = snapshotRefs
      .map((ref) => {
        const taskMeta = snapshotIndex[ref];
        if (!taskMeta || taskMeta.type !== "TASK") {
          return null;
        }
        const parentKr = taskMeta.parent ? snapshotIndex[taskMeta.parent] : null;
        const parentKrScore =
          parentKr && parentKr.type === "KEY_RESULT"
            ? clampProgress((parentKr.node as AtlasKeyResultSnapshot).ai_overall_score)
            : null;
        const task = taskMeta.node as AtlasTaskSnapshot;
        const deadlineTs = task.deadline ? new Date(task.deadline).getTime() : Number.POSITIVE_INFINITY;
        const urgencyBonus = Number.isFinite(deadlineTs)
          ? Math.max(0, Math.round((Date.now() - deadlineTs) / (1000 * 60 * 60 * 24)))
          : 0;
        const priorityScore = (100 - clampProgress(taskMeta.progress))
          + urgencyBonus
          + (parentKrScore ? (100 - parentKrScore) / 4 : 0);
        return {
          task_ref: ref,
          title: taskMeta.title,
          progress: clampProgress(taskMeta.progress),
          status: String(task.status || "IN_PROGRESS"),
          deadline: task.deadline || null,
          path: taskMeta.path.map((pathRef) => snapshotIndex[pathRef]?.title || pathRef).join(" > "),
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
        "You are a task prioritization assistant.",
        "Given a list of tasks, pick the single best next task to work on.",
        "You MUST return strict JSON with exactly these keys: task_ref, reason, confidence.",
        "task_ref: copy the exact task_ref string from the candidates (e.g. 'task_1'). Do NOT invent new refs.",
        "reason: one sentence explaining why this task is the best next action.",
        "confidence: an integer from 0 to 100.",
        "Candidates:",
        JSON.stringify(candidates, null, 0),
      ].join("\n");
      const submitted = await submitBackendJob({
        actor_username: user.username,
        kind: "ai.generate_json",
        payload: { prompt },
      });
      const done = await waitForBackendJobResult(user, submitted.id);
      if (String(done.status || "").toLowerCase() !== "succeeded") {
        throw new Error(String(done.error_text || "AI suggestion failed."));
      }
      const result = (done.result || {}) as Record<string, unknown>;
      let pickedRef = String(result.task_ref || "").trim().replace(/^["']|["']$/g, "");
      // If AI returned empty, fall back to top-priority candidate.
      if (!pickedRef && candidates.length > 0) {
        pickedRef = candidates[0].task_ref;
      }
      // Normalize: AI may return bare ID, "Task 123", or title instead of "task_123".
      if (pickedRef && !snapshotRefs.includes(pickedRef) && !snapshotIndex[pickedRef]) {
        const stripped = pickedRef.replace(/^(task|Task)\s*/i, "").trim();
        const numericId = Number.parseInt(stripped, 10);
        if (Number.isFinite(numericId) && numericId > 0) {
          const normalized = `task_${numericId}`;
          if (snapshotRefs.includes(normalized)) {
            pickedRef = normalized;
          }
        }
      }
      // Last resort: fuzzy match by title.
      if (pickedRef && !snapshotRefs.includes(pickedRef) && !snapshotIndex[pickedRef]) {
        const lower = pickedRef.toLowerCase();
        const match = snapshotRefs.find((ref) => {
          const meta = snapshotIndex[ref];
          return meta && String(meta.title || "").toLowerCase() === lower;
        });
        if (match) {
          pickedRef = match;
        }
      }
      if (!pickedRef || !snapshotRefs.includes(pickedRef) || !snapshotIndex[pickedRef]) {
        const aiRaw = String(result.task_ref || "");
        throw new Error(
          `AI returned an invalid task_ref outside current scope. AI raw: "${aiRaw}", available refs: ${snapshotRefs.slice(0, 5).join(", ")}${snapshotRefs.length > 5 ? "..." : ""}`,
        );
      }
      const reason = String(result.reason || "").trim();
      const confidenceRaw = Number(result.confidence);
      const confidence = Number.isFinite(confidenceRaw) ? clampProgress(confidenceRaw) : null;
      onTaskSuggested(pickedRef);
      setAiSuggestion({
        taskRef: pickedRef,
        reason,
        confidence,
      });
      setAiSyncMessage(`Suggested next task: ${snapshotIndex[pickedRef]?.title || pickedRef}`);
    } catch (error) {
      setAiSyncError(String(error instanceof Error ? error.message : error));
    } finally {
      setAiSuggestPending(false);
    }
  }, [atlasRuntime, onTaskSuggested, taskRefs, user]);

  return {
    aiSyncPending,
    aiSyncError,
    aiSyncMessage,
    aiSyncReport,
    aiProgressUndoItems,
    aiSuggestPending,
    aiSuggestion,
    handleAiProgressSync,
    handleAiProgressUndo,
    handleAiSuggestNextTask,
  };
}
