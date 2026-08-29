"use client";

import { useCallback, useState, type Dispatch, type SetStateAction } from "react";

import { readCyclesQuery, type AuthUser, type CycleSummary } from "@/lib/api";

type UseCyclesSourceInput = {
  user: AuthUser | null;
  setSessionCycles: Dispatch<SetStateAction<CycleSummary[]>>;
};

export type CyclesSource = {
  /** Fetch cycles.all + cycles.active in parallel; merge into one list. */
  refreshCycles: (activeUser: AuthUser) => Promise<CycleSummary[]>;
  pending: boolean;
};

/**
 * Single source of truth for the Atlas cycle list.
 *
 * Fetches `cycles.all` (dropdown contents) and `cycles.active` (the
 * authoritative admin-activated cycle) in parallel and merges them so the
 * active cycle can never be missing from the top bar.
 */
export default function useCyclesSource({
  user,
  setSessionCycles,
}: UseCyclesSourceInput): CyclesSource {
  const [pending, setPending] = useState(false);

  const refreshCycles = useCallback(
    async (activeUser: AuthUser): Promise<CycleSummary[]> => {
      setPending(true);
      try {
        const [allCycles, activeCycles] = await Promise.all([
          readCyclesQuery({
            actor_username: activeUser.username,
            kind: "cycles.all",
          }),
          readCyclesQuery({
            actor_username: activeUser.username,
            kind: "cycles.active",
          }).catch(() => [] as CycleSummary[]),
        ]);
        const mergedById = new Map<number, CycleSummary>();
        for (const cycle of allCycles) {
          mergedById.set(cycle.id, cycle);
        }
        for (const activeCycle of activeCycles) {
          if (!mergedById.has(activeCycle.id)) {
            mergedById.set(activeCycle.id, activeCycle);
          }
        }
        const merged = [...mergedById.values()].sort(
          (left, right) => right.id - left.id,
        );
        setSessionCycles(merged);
        return merged;
      } finally {
        setPending(false);
      }
    },
    [setSessionCycles],
  );

  return { refreshCycles, pending };
}
