"use client";

import { useCallback, useState, type Dispatch, type SetStateAction } from "react";

import { type AuthUser, type CycleSummary } from "@/lib/api";
import { readMergedCycles } from "@/lib/cycles";

type UseCyclesSourceInput = {
  user: AuthUser | null;
  setSessionCycles: Dispatch<SetStateAction<CycleSummary[]>>;
};

export type CyclesSource = {
  /** Fetch cycles.all + cycles.active in parallel; merge into one list. */
  refreshCycles: (
    activeUser: AuthUser,
    options?: { bypassCache?: boolean },
  ) => Promise<CycleSummary[]>;
  pending: boolean;
};

/**
 * Single source of truth for the Atlas cycle list.
 *
 * Fetches `cycles.all` (dropdown contents) and `cycles.active` (the
 * authoritative admin-activated cycle) in parallel and merges them so the
 * active cycle can never be missing from the top bar.
 *
 * Reads go through the shared cycle cache via `readMergedCycles`, so this hook
 * and the deep-link bootstrap hook issue one request pair between them instead
 * of one each. Mutation paths pass `bypassCache: true`; the fresh result is
 * written through the cache, so a sibling reader that follows gets the new value
 * instead of issuing a second request.
 */
export default function useCyclesSource({
  setSessionCycles,
}: UseCyclesSourceInput): CyclesSource {
  const [pending, setPending] = useState(false);

  const refreshCycles = useCallback(
    async (
      activeUser: AuthUser,
      options: { bypassCache?: boolean } = {},
    ): Promise<CycleSummary[]> => {
      setPending(true);
      try {
        const merged = await readMergedCycles(activeUser.username, {
          bypassCache: options.bypassCache,
        });
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
