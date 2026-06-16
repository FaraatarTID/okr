"use client";

import { useCallback, useEffect, useState } from "react";

import {
  createCheckInMutation,
  closeExperimentMutation,
  createExperimentMutation,
  updateExperimentMutation,
  type AuthUser,
  type ExperimentDecisionType,
  type ExperimentMutationResponse,
} from "@/lib/api";
import { parseNumberOrNull } from "@/components/atlas-shell/shellAnalyticsUtils";

type CheckInDraft = {
  value: string;
  confidence: "CONFIDENT" | "UNCERTAIN";
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

type ExperimentCloseDraft = {
  decision: ExperimentDecisionType;
  rationale: string;
};

type KeyResultReadLike = {
  id: number;
  progress?: number | null;
  current_value?: number | null;
};

type ExperimentReadLike = {
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

type UseRitualActionsInput = {
  user: AuthUser | null;
  parsedCycleId: number | null;
  ritualKrs: KeyResultReadLike[];
  ritualExperimentsByKr: Record<number, ExperimentReadLike[]>;
  loadModeData: (activeUser: AuthUser, mode: string) => Promise<void>;
  loadSnapshotForUser: (activeUser: AuthUser) => Promise<void>;
  appendRitualExperiment: (krId: number, experiment: ExperimentReadLike) => void;
};

export default function useRitualActions({
  user,
  parsedCycleId,
  ritualKrs,
  ritualExperimentsByKr,
  loadModeData,
  loadSnapshotForUser,
  appendRitualExperiment,
}: UseRitualActionsInput) {
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
          confidence: "CONFIDENT",
          comment: "",
          variationType: "COMMON_CAUSE",
          specialCauseNote: "",
          experimentId: "",
        };
      }
      return next;
    });
  }, [ritualKrs]);

  const updateRitualCheckInDraft = useCallback((krId: number, patch: Partial<CheckInDraft>): void => {
    setRitualCheckInError((prev) => ({ ...prev, [krId]: "" }));
    setRitualCheckInMessage((prev) => ({ ...prev, [krId]: "" }));
    setRitualCheckInDrafts((prev) => {
      const base = prev[krId] || {
        value: "0",
        confidence: "CONFIDENT",
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
  }, []);

  const updateRitualExperimentDraft = useCallback((krId: number, patch: Partial<ExperimentDraft>): void => {
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
  }, []);

  const updateRitualExperimentCloseDraft = useCallback((
    experimentId: number,
    patch: Partial<ExperimentCloseDraft>,
  ): void => {
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
  }, []);

  const handleRitualExperimentStart = useCallback(async (experimentId: number): Promise<void> => {
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
  }, [loadModeData, loadSnapshotForUser, parsedCycleId, user]);

  const handleRitualExperimentClose = useCallback(async (experimentId: number): Promise<void> => {
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
  }, [loadModeData, loadSnapshotForUser, parsedCycleId, ritualExperimentCloseDrafts, user]);

  const handleRitualExperimentCreate = useCallback(async (kr: KeyResultReadLike): Promise<void> => {
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
      const createdRow: ExperimentReadLike = {
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
      appendRitualExperiment(krId, createdRow);
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
  }, [appendRitualExperiment, parsedCycleId, ritualExperimentDrafts, user]);

  const handleRitualCheckInSubmit = useCallback(async (kr: KeyResultReadLike): Promise<void> => {
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
    if (!Number.isFinite(value)) {
      setRitualCheckInError((prev) => ({ ...prev, [krId]: "Check-in value must be numeric." }));
      return;
    }
    const confidenceScore = draft.confidence === "UNCERTAIN" ? 0 : 10;
    const comment = draft.comment.trim();
    if (draft.confidence === "UNCERTAIN" && !comment) {
      setRitualCheckInError((prev) => ({
        ...prev,
        [krId]: "Uncertain check-ins require a comment explaining risks and next action.",
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
        confidence: confidenceScore,
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
  }, [loadModeData, loadSnapshotForUser, parsedCycleId, ritualCheckInDrafts, ritualExperimentsByKr, user]);

  return {
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
  };
}
