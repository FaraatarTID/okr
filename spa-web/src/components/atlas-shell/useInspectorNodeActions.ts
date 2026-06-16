"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import type { AtlasIndexNode, AtlasKeyResultSnapshot } from "@/lib/atlas";
import {
  analyzeNodeAi,
  createNodeMutation,
  deleteNodeMutation,
  updateNodeMutation,
  type AuthUser,
  type NodeTypePath,
} from "@/lib/api";
import { nodeTypeLabel } from "@/lib/atlas";
import { mutationNodeRef, nodeTypeToPath } from "@/components/atlas-shell/nodeMutation";
import {
  parseAnalysisSummary,
  type AnalysisSummaryView,
} from "@/components/atlas-shell/shellAnalyticsUtils";

export type InspectorEditDraft = {
  title: string;
  description: string;
  progress: string;
  startValue: string;
  targetValue: string;
  deadline: string;
  estimatedMinutes: string;
};

export type NodeCreateDraft = {
  createType: NodeTypePath;
  title: string;
  description: string;
  cycleId: string;
  tags: string;
  targetValue: string;
  unit: string;
  estimatedMinutes: string;
  deadline: string;
};

type CreateContext = {
  goalId: number | null;
  objectiveId: number | null;
  keyResultId: number | null;
};

type UseInspectorNodeActionsInput = {
  user: AuthUser | null;
  selectedMeta: AtlasIndexNode | null;
  parsedCycleId: number | null;
  createContext: CreateContext;
  focusTaskRef: string;
  loadSnapshotForUser: (activeUser: AuthUser) => Promise<void>;
  setSelectedRef: (nextRef: string) => void;
  setFocusTaskRef: (nextRef: string) => void;
};

export default function useInspectorNodeActions({
  user,
  selectedMeta,
  parsedCycleId,
  createContext,
  focusTaskRef,
  loadSnapshotForUser,
  setSelectedRef,
  setFocusTaskRef,
}: UseInspectorNodeActionsInput) {
  const [inspectPending, setInspectPending] = useState(false);
  const [inspectError, setInspectError] = useState("");
  const [inspectMessage, setInspectMessage] = useState("");
  const [inspectAnalysisPending, setInspectAnalysisPending] = useState(false);
  const [inspectAnalysisError, setInspectAnalysisError] = useState("");
  const [inspectAnalysis, setInspectAnalysis] = useState<AnalysisSummaryView | null>(null);
  const [inspectDraft, setInspectDraft] = useState<InspectorEditDraft>({
    title: "",
    description: "",
    progress: "",
    startValue: "",
    targetValue: "",
    deadline: "",
    estimatedMinutes: "",
  });
  const [createPending, setCreatePending] = useState(false);
  const [createError, setCreateError] = useState("");
  const [createMessage, setCreateMessage] = useState("");
  const [createDraft, setCreateDraft] = useState<NodeCreateDraft>({
    createType: "goal",
    title: "",
    description: "",
    cycleId: "",
    tags: "",
    targetValue: "100",
    unit: "%",
    estimatedMinutes: "30",
    deadline: "",
  });
  const [deletePending, setDeletePending] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const [deleteMessage, setDeleteMessage] = useState("");
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

  useEffect(() => {
    if (!selectedMeta) {
      setInspectAnalysis(null);
      setInspectAnalysisError("");
      return;
    }
    if (selectedMeta.type === "KEY_RESULT") {
      const keyResult = selectedMeta.node as AtlasKeyResultSnapshot;
      setInspectAnalysis(parseAnalysisSummary(keyResult.ai_analysis || null));
      setInspectAnalysisError("");
      return;
    }
    setInspectAnalysis(null);
    setInspectAnalysisError("");
  }, [selectedMeta]);

  useEffect(() => {
    if (!selectedMeta) {
      setInspectDraft({
        title: "",
        description: "",
        progress: "",
        startValue: "",
        targetValue: "",
        deadline: "",
        estimatedMinutes: "",
      });
      setCreateError("");
      setCreateMessage("");
      setDeleteError("");
      setDeleteMessage("");
      return;
    }
    const taskNode = selectedMeta.node as unknown as Record<string, unknown>;
    const rawDeadline = taskNode.deadline || taskNode.due_date || "";
    const deadlineStr = rawDeadline ? String(rawDeadline).slice(0, 10) : "";
    const estimatedMin = taskNode.estimated_minutes != null
      ? String(taskNode.estimated_minutes)
      : "";
    setInspectDraft({
      title: selectedMeta.title,
      description: selectedMeta.description,
      progress: `${selectedMeta.progress}`,
      startValue: taskNode.start_value != null ? String(taskNode.start_value) : "",
      targetValue: taskNode.target_value != null ? String(taskNode.target_value) : "",
      deadline: deadlineStr,
      estimatedMinutes: estimatedMin,
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

  const handleInspectorRunAnalysis = useCallback(async (): Promise<void> => {
    if (!user || !selectedMeta) {
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
          ai_analysis: analysis.raw || analysisRaw,
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
  }, [loadSnapshotForUser, parsedCycleId, user, selectedMeta, user]);

  const handleInspectorSave = useCallback(async (): Promise<void> => {
    if (!user || !selectedMeta) {
      return;
    }
    const parsedProgress = Number.parseInt(inspectDraft.progress, 10);
    const isTask = selectedMeta.type === "TASK";
    if (!Number.isFinite(parsedProgress) || parsedProgress < 0 || (!isTask && parsedProgress > 100)) {
      setInspectError(isTask
        ? "Progress must be a non-negative integer."
        : "Progress must be an integer between 0 and 100.");
      setInspectMessage("");
      return;
    }

    setInspectPending(true);
    setInspectError("");
    setInspectMessage("");
    try {
      const updates: Record<string, unknown> = {
          title: inspectDraft.title.trim(),
          description: inspectDraft.description.trim(),
          progress: parsedProgress,
        };
        const deadlineVal = inspectDraft.deadline.trim();
        if (deadlineVal) {
          updates.deadline = deadlineVal;
        } else {
          updates.deadline = null;
        }
        if (isTask) {
          const estMin = Number.parseInt(inspectDraft.estimatedMinutes, 10);
          updates.estimated_minutes = Number.isFinite(estMin) && estMin >= 0 ? estMin : 0;
        }
        if (selectedMeta.type === "KEY_RESULT") {
          const sv = inspectDraft.startValue.trim();
          const tv = inspectDraft.targetValue.trim();
          updates.start_value = sv !== "" ? Number(sv) : null;
          updates.target_value = tv !== "" ? Number(tv) : null;
        }
        await updateNodeMutation({
        actor_username: user.username,
        node_type: nodeTypeToPath(selectedMeta.type),
        node_id: selectedMeta.id,
        updates,
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
  }, [inspectDraft.deadline, inspectDraft.description, inspectDraft.estimatedMinutes, inspectDraft.progress, inspectDraft.title, loadSnapshotForUser, parsedCycleId, user, selectedMeta]);

  const handleNodeCreate = useCallback(async (): Promise<void> => {
    if (!user) {
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

      const deadlineCandidate = createDraft.deadline.trim();
      if (deadlineCandidate) {
        payload.deadline = deadlineCandidate;
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
  }, [canCreateForContext, createContext.goalId, createContext.keyResultId, createContext.objectiveId, createDraft, loadSnapshotForUser, parsedCycleId, user, setSelectedRef, user]);

  const handleNodeDelete = useCallback(async (): Promise<void> => {
    if (!user || !selectedMeta) {
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
  }, [focusTaskRef, loadSnapshotForUser, parsedCycleId, user, selectedMeta, setFocusTaskRef, setSelectedRef, user]);

  return {
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
    createDraft,
    setCreateDraft,
    deletePending,
    deleteError,
    deleteMessage,
    canCreateForContext,
    handleInspectorRunAnalysis,
    handleInspectorSave,
    handleNodeCreate,
    handleNodeDelete,
  };
}
