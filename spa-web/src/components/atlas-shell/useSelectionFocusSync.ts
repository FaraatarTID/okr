"use client";

import { useEffect, type Dispatch, type SetStateAction } from "react";

type AtlasRuntimeView = {
  roots: string[];
  index: Record<string, unknown>;
} | null;

type SelectedMetaView = {
  type: string;
  ref: string;
} | null;

type UseSelectionFocusSyncInput<TCreateDraft extends { cycleId: string }> = {
  atlasRuntime: AtlasRuntimeView;
  selectedRef: string;
  setSelectedRef: Dispatch<SetStateAction<string>>;
  taskRefs: string[];
  focusTaskRef: string;
  setFocusTaskRef: Dispatch<SetStateAction<string>>;
  selectedMeta: SelectedMetaView;
  cycleId: string;
  setCreateDraft: Dispatch<SetStateAction<TCreateDraft>>;
};

export default function useSelectionFocusSync<TCreateDraft extends { cycleId: string }>({
  atlasRuntime,
  selectedRef,
  setSelectedRef,
  taskRefs,
  focusTaskRef,
  setFocusTaskRef,
  selectedMeta,
  cycleId,
  setCreateDraft,
}: UseSelectionFocusSyncInput<TCreateDraft>) {
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
  }, [atlasRuntime, selectedRef, setSelectedRef]);

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
  }, [focusTaskRef, setFocusTaskRef, taskRefs]);

  useEffect(() => {
    if (selectedMeta?.type === "TASK" && selectedMeta.ref !== focusTaskRef) {
      setFocusTaskRef(selectedMeta.ref);
    }
  }, [focusTaskRef, selectedMeta, setFocusTaskRef]);

  useEffect(() => {
    setCreateDraft((prev) => {
      if (prev.cycleId.trim()) {
        return prev;
      }
      return {
        ...prev,
        cycleId,
      };
    });
  }, [cycleId, setCreateDraft]);
}
