"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import type { AtlasIndexNode } from "@/lib/atlas";
import {
  createAlignmentMutation,
  createObjectiveAlignmentLinkMutation,
  deleteAlignmentMutation,
  deleteObjectiveAlignmentLinkMutation,
  deleteWorkLogMutation,
  readBackendQuery,
  type AuthUser,
} from "@/lib/api";
import type { ReadQueryWorkLog } from "@/lib/api/backend-schema";

type WorkLogRead = ReadQueryWorkLog;

type AlignmentContextPayload = {
  parents?: Array<{ id: number; title?: string }>;
  children?: Array<{ id: number; title?: string }>;
  all_objectives?: Array<{ id: number; title?: string }>;
  edges?: Array<{ id: number; parent_id: number; child_id: number; alignment_type?: string }>;
  available_goals?: Array<{ id: number; title?: string }>;
  available_key_results?: Array<{ id: number; title?: string }>;
  objective_links?: Array<{
    id: number;
    objective_id: number;
    linked_entity_type: string;
    linked_entity_id: number;
    direction: string;
    created_at?: string;
    created_by?: string;
  }>;
};

type UseInspectorAuxDataInput = {
  user: AuthUser | null;
  selectedMeta: AtlasIndexNode | null;
  parsedCycleId: number | null;
  loadSnapshotForUser: (activeUser: AuthUser) => Promise<void>;
};

function parseDateOrNull(value: string | null | undefined): Date | null {
  if (!value || typeof value !== "string") {
    return null;
  }
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export default function useInspectorAuxData({
  user,
  selectedMeta,
  parsedCycleId,
  loadSnapshotForUser,
}: UseInspectorAuxDataInput) {
  const [alignmentContext, setAlignmentContext] = useState<AlignmentContextPayload | null>(null);
  const [alignmentPending, setAlignmentPending] = useState(false);
  const [alignmentError, setAlignmentError] = useState("");
  const [alignmentTargetObjectiveId, setAlignmentTargetObjectiveId] = useState("");
  const [alignmentDirection, setAlignmentDirection] = useState<"parent" | "child">("parent");
  const [alignmentType, setAlignmentType] = useState("SUPPORTS");
  const [objLinkDirection, setObjLinkDirection] = useState<"parent" | "child">("parent");
  const [objLinkTargetId, setObjLinkTargetId] = useState("");
  const [objLinkPending, setObjLinkPending] = useState(false);
  const [objLinkError, setObjLinkError] = useState("");
  const [inspectTaskWorkLogs, setInspectTaskWorkLogs] = useState<WorkLogRead[]>([]);
  const [inspectTaskWorkLogsPending, setInspectTaskWorkLogsPending] = useState(false);
  const [inspectTaskWorkLogsError, setInspectTaskWorkLogsError] = useState("");
  const [inspectTaskWorkLogPendingId, setInspectTaskWorkLogPendingId] = useState<number | null>(null);
  const [inspectTaskWorkLogsActionError, setInspectTaskWorkLogsActionError] = useState("");
  const [inspectTaskWorkLogsActionMessage, setInspectTaskWorkLogsActionMessage] = useState("");

  const inspectTaskWorkHistoryRows = useMemo(() => {
    if (!inspectTaskWorkLogs.length) {
      return [];
    }
    return [...inspectTaskWorkLogs].sort((left, right) => {
      const leftAt =
        parseDateOrNull(left.end_time || left.start_time)?.getTime() ?? Number.NEGATIVE_INFINITY;
      const rightAt =
        parseDateOrNull(right.end_time || right.start_time)?.getTime() ?? Number.NEGATIVE_INFINITY;
      return rightAt - leftAt;
    });
  }, [inspectTaskWorkLogs]);

  const loadAlignmentContext = useCallback(async (activeUser: AuthUser, objectiveId: number): Promise<void> => {
    setAlignmentPending(true);
    setAlignmentError("");
    try {
      const payload = await readBackendQuery({
        actor_username: activeUser.username,
        kind: "alignments.context",
        params: { objective_id: objectiveId },
      });
      setAlignmentContext((payload || null) as AlignmentContextPayload | null);
    } catch (error) {
      setAlignmentError(String(error instanceof Error ? error.message : error));
      setAlignmentContext(null);
    } finally {
      setAlignmentPending(false);
    }
  }, []);

  const loadInspectorTaskWorkLogs = useCallback(async (activeUser: AuthUser, taskId: number): Promise<void> => {
    setInspectTaskWorkLogsPending(true);
    setInspectTaskWorkLogsError("");
    try {
      const payload = await readBackendQuery({
        actor_username: activeUser.username,
        kind: "work_logs.by_task",
        params: { task_id: taskId },
      });
      setInspectTaskWorkLogs((payload.work_logs || []).slice(0, 200));
    } catch (error) {
      setInspectTaskWorkLogsError(String(error instanceof Error ? error.message : error));
      setInspectTaskWorkLogs([]);
    } finally {
      setInspectTaskWorkLogsPending(false);
    }
  }, []);

  const handleInspectorDeleteWorkLog = useCallback(
    async (workLogId: number): Promise<void> => {
      if (!user || !selectedMeta || selectedMeta.type !== "TASK") {
        return;
      }
      if (typeof window !== "undefined") {
        const confirmed = window.confirm(`Delete work log #${workLogId}? This cannot be undone.`);
        if (!confirmed) {
          return;
        }
      }
      setInspectTaskWorkLogPendingId(workLogId);
      setInspectTaskWorkLogsActionError("");
      setInspectTaskWorkLogsActionMessage("");
      try {
        await deleteWorkLogMutation({
          actor_username: user.username,
          work_log_id: workLogId,
        });
        setInspectTaskWorkLogsActionMessage(`Deleted work log #${workLogId}.`);
        await loadInspectorTaskWorkLogs(user, selectedMeta.id);
        if (parsedCycleId) {
          await loadSnapshotForUser(user);
        }
      } catch (error) {
        setInspectTaskWorkLogsActionError(String(error instanceof Error ? error.message : error));
      } finally {
        setInspectTaskWorkLogPendingId((current) => (current === workLogId ? null : current));
      }
    },
    [loadInspectorTaskWorkLogs, loadSnapshotForUser, parsedCycleId, selectedMeta, user],
  );

  const handleAlignmentCreate = useCallback(async (): Promise<void> => {
    if (!user || !selectedMeta || selectedMeta.type !== "OBJECTIVE") {
      return;
    }
    const targetId = Number.parseInt(alignmentTargetObjectiveId, 10);
    if (!Number.isFinite(targetId) || targetId <= 0) {
      setAlignmentError("Choose a valid objective to link.");
      return;
    }
    try {
      const parentId = alignmentDirection === "parent" ? targetId : selectedMeta.id;
      const childId = alignmentDirection === "parent" ? selectedMeta.id : targetId;
      await createAlignmentMutation({
        actor_username: user.username,
        parent_id: parentId,
        child_id: childId,
        alignment_type: alignmentType,
      });
      await loadAlignmentContext(user, selectedMeta.id);
      setAlignmentTargetObjectiveId("");
      setAlignmentError("");
    } catch (error) {
      setAlignmentError(String(error instanceof Error ? error.message : error));
    }
  }, [alignmentDirection, alignmentTargetObjectiveId, alignmentType, loadAlignmentContext, selectedMeta, user]);

  const handleAlignmentDelete = useCallback(
    async (edgeId: number): Promise<void> => {
      if (!user || !selectedMeta || selectedMeta.type !== "OBJECTIVE") {
        return;
      }
      try {
        await deleteAlignmentMutation({
          actor_username: user.username,
          edge_id: edgeId,
        });
        await loadAlignmentContext(user, selectedMeta.id);
        setAlignmentError("");
      } catch (error) {
        setAlignmentError(String(error instanceof Error ? error.message : error));
      }
    },
    [loadAlignmentContext, selectedMeta, user],
  );

  const handleObjectiveAlignmentLinkCreate = useCallback(async (): Promise<void> => {
    if (!user || !selectedMeta || selectedMeta.type !== "OBJECTIVE") {
      return;
    }
    const targetId = Number.parseInt(objLinkTargetId, 10);
    if (!Number.isFinite(targetId) || targetId <= 0) {
      setObjLinkError("Choose a valid target to link.");
      return;
    }
    const linkedEntityType = objLinkDirection === "parent" ? "goal" : "key_result";
    try {
      await createObjectiveAlignmentLinkMutation({
        actor_username: user.username,
        objective_id: selectedMeta.id,
        linked_entity_type: linkedEntityType,
        linked_entity_id: targetId,
        direction: objLinkDirection,
      });
      await loadAlignmentContext(user, selectedMeta.id);
      setObjLinkTargetId("");
      setObjLinkError("");
    } catch (error) {
      setObjLinkError(String(error instanceof Error ? error.message : error));
    }
  }, [objLinkDirection, objLinkTargetId, loadAlignmentContext, selectedMeta, user]);

  const handleObjectiveAlignmentLinkDelete = useCallback(
    async (linkId: number): Promise<void> => {
      if (!user || !selectedMeta || selectedMeta.type !== "OBJECTIVE") {
        return;
      }
      try {
        await deleteObjectiveAlignmentLinkMutation({
          actor_username: user.username,
          link_id: linkId,
        });
        await loadAlignmentContext(user, selectedMeta.id);
        setObjLinkError("");
      } catch (error) {
        setObjLinkError(String(error instanceof Error ? error.message : error));
      }
    },
    [loadAlignmentContext, selectedMeta, user],
  );

  useEffect(() => {
    if (!user || !selectedMeta || selectedMeta.type !== "OBJECTIVE") {
      setAlignmentContext(null);
      return;
    }
    void loadAlignmentContext(user, selectedMeta.id);
  }, [loadAlignmentContext, selectedMeta, user]);

  useEffect(() => {
    if (!user || !selectedMeta || selectedMeta.type !== "TASK") {
      setInspectTaskWorkLogs([]);
      setInspectTaskWorkLogsPending(false);
      setInspectTaskWorkLogsError("");
      setInspectTaskWorkLogPendingId(null);
      setInspectTaskWorkLogsActionError("");
      setInspectTaskWorkLogsActionMessage("");
      return;
    }
    setInspectTaskWorkLogPendingId(null);
    setInspectTaskWorkLogsActionError("");
    setInspectTaskWorkLogsActionMessage("");
    void loadInspectorTaskWorkLogs(user, selectedMeta.id);
  }, [loadInspectorTaskWorkLogs, selectedMeta, user]);

  return {
    alignmentContext,
    alignmentPending,
    alignmentError,
    alignmentTargetObjectiveId,
    alignmentDirection,
    alignmentType,
    setAlignmentTargetObjectiveId,
    setAlignmentDirection,
    setAlignmentType,
    objLinkDirection,
    setObjLinkDirection,
    objLinkTargetId,
    setObjLinkTargetId,
    objLinkPending,
    objLinkError,
    handleObjectiveAlignmentLinkCreate,
    handleObjectiveAlignmentLinkDelete,
    inspectTaskWorkLogsPending,
    inspectTaskWorkLogsError,
    inspectTaskWorkLogPendingId,
    inspectTaskWorkLogsActionError,
    inspectTaskWorkLogsActionMessage,
    inspectTaskWorkHistoryRows,
    handleInspectorDeleteWorkLog,
    handleAlignmentCreate,
    handleAlignmentDelete,
  };
}
