"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  analyzeNodeAi,
  submitBackendJob,
  type AuthUser,
} from "@/lib/api";
import { isAnalysisStale, clampProgress } from "@/components/atlas-shell/shellAnalyticsUtils";
import { waitForBackendJobResult } from "@/components/atlas-shell/jobPolling";
import type {
  AtlasIndexNode,
  AtlasKeyResultSnapshot,
  AtlasTaskSnapshot,
} from "@/lib/atlas";

type AtlasRuntimeLike = {
  index: Record<string, AtlasIndexNode>;
};

export type AiAnalysisReport = {
  total: number;
  analyzed: number;
  reanalyzed: number;
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
  loadSnapshotForUser: (activeUser: AuthUser) => Promise<void>;
  onTaskSuggested: (taskRef: string) => void;
};

export default function useAiProgressAssist({
  user,
  parsedCycleId,
  atlasRuntime,
  allScopeRefs,
  taskRefs,
  loadSnapshotForUser,
  onTaskSuggested,
}: UseAiProgressAssistInput) {
  const [aiSyncPending, setAiSyncPending] = useState(false);
  const [aiSyncError, setAiSyncError] = useState("");
  const [aiSyncMessage, setAiSyncMessage] = useState("");
  const [aiSyncReport, setAiSyncReport] = useState<AiAnalysisReport | null>(null);
  const [aiSuggestPending, setAiSuggestPending] = useState(false);
  const [aiSuggestion, setAiSuggestion] = useState<AiTaskSuggestion | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    setAiSyncReport(null);
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
      let reanalyzed = 0;
      let unchanged = 0;
      const failed: string[] = [];

      const BATCH_SIZE = 3;
      for (let i = 0; i < krRefs.length; i += BATCH_SIZE) {
        const batch = krRefs.slice(i, i + BATCH_SIZE);
        const results = await Promise.allSettled(
          batch.map(async (ref) => {
            const meta = atlasRuntime.index[ref];
            if (!meta || meta.type !== "KEY_RESULT") return;
            const krNode = meta.node as AtlasKeyResultSnapshot;
            if (
              krNode.ai_overall_score != null &&
              !isAnalysisStale(krNode.analysis_updated_at)
            ) {
              unchanged += 1;
              return;
            }
            const analysisRaw = await analyzeNodeAi({
              actor_username: user.username,
              node_id: meta.id,
              node_type: "KEY_RESULT",
            });
            await import("@/lib/api").then(({ updateNodeMutation }) =>
              updateNodeMutation({
                actor_username: user.username,
                node_type: "key_result",
                node_id: meta.id,
                updates: { ai_analysis: analysisRaw },
              }),
            );
            reanalyzed += 1;
          }),
        );
        results.forEach((r, idx) => {
          if (r.status === "rejected") {
            failed.push(`${batch[idx]}: ${String(r.reason || "analysis failed")}`);
          }
        });
        analyzed += batch.length;
      }

      if (reanalyzed > 0 && parsedCycleId) {
        await loadSnapshotForUser(user);
      }

      setAiSyncReport({
        total: krRefs.length,
        analyzed,
        reanalyzed,
        unchanged,
        failed: failed.slice(0, 8),
      });

      if (previewOnly) {
        if (reanalyzed > 0) {
          setAiSyncMessage(`Analyzed ${reanalyzed} KR${reanalyzed !== 1 ? "s" : ""} (${unchanged} cached).`);
        } else {
          setAiSyncMessage(`All ${krRefs.length} KRs already have fresh analysis.`);
        }
      } else {
        if (reanalyzed > 0) {
          setAiSyncMessage(`Analysis complete for ${reanalyzed} KR${reanalyzed !== 1 ? "s" : ""}.`);
        } else {
          setAiSyncMessage(`No new analysis needed. All ${krRefs.length} KRs are up to date.`);
        }
      }

      if (parsedCycleId) {
        await loadSnapshotForUser(user);
      }
    } catch (error) {
      setAiSyncError(String(error instanceof Error ? error.message : error));
    } finally {
      setAiSyncPending(false);
    }
  }, [allScopeRefs, atlasRuntime, loadSnapshotForUser, parsedCycleId, user]);

  const handleAiSuggestNextTask = useCallback(async (): Promise<void> => {
    if (!user || !atlasRuntime) {
      return;
    }
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
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
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
      const done = await waitForBackendJobResult(user, submitted.id, { signal: controller.signal });
      if (String(done.status || "").toLowerCase() !== "succeeded") {
        throw new Error(String(done.error_text || "AI suggestion failed."));
      }
      const result = (done.result || {}) as Record<string, unknown>;
      let pickedRef = String(result.task_ref || "").trim().replace(/^["']|["']$/g, "");
      if (!pickedRef && candidates.length > 0) {
        pickedRef = candidates[0].task_ref;
      }
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
      if (error instanceof DOMException && error.name === "AbortError") return;
      setAiSyncError(String(error instanceof Error ? error.message : error));
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
      }
      setAiSuggestPending(false);
    }
  }, [atlasRuntime, onTaskSuggested, taskRefs, user]);

  return {
    aiSyncPending,
    aiSyncError,
    aiSyncMessage,
    aiSyncReport,
    aiSuggestPending,
    aiSuggestion,
    handleAiProgressSync,
    handleAiSuggestNextTask,
  };
}
