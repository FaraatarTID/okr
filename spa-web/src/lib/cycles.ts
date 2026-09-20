import { readCyclesQuery, type CycleSummary } from "@/lib/api";
import { cacheKeys, readThroughCache } from "@/lib/resourceCache";

/** The two query kinds the shell combines into one visible cycle list. */
export type CyclePair = {
  all: CycleSummary[];
  active: CycleSummary[];
};

/**
 * Read and cache the `cycles.all` + `cycles.active` pair.
 *
 * Both requests are issued in parallel, which preserves the existing behaviour
 * where a failure of `cycles.active` degrades to an empty list instead of
 * failing the read. A failure of `cycles.all` is a real failure and propagates.
 *
 * Both hooks that need the pair go through here, so the duplicate request is
 * collapsed to one per TTL window. Any mutation that changes the cycle list must
 * re-read with `bypassCache: true`, which skips the stale entry and writes the
 * fresh result back; `clearResourceCache` is reserved for whole-cache events.
 */
export function readCyclesPair(
  username: string,
  options: { bypassCache?: boolean; ttlMs?: number } = {},
): Promise<CyclePair> {
  return readThroughCache(
    cacheKeys.cycles(username),
    async () => {
      const [all, active] = await Promise.all([
        readCyclesQuery({ actor_username: username, kind: "cycles.all" }),
        readCyclesQuery({ actor_username: username, kind: "cycles.active" }).catch(
          () => [] as CycleSummary[],
        ),
      ]);
      return { all, active };
    },
    options,
  );
}

/**
 * Merge the pair into the single list the shell renders.
 *
 * Every active cycle is guaranteed to be present even if `cycles.all` was stale
 * or scope-filtered it out, and the result is ordered by descending id.
 */
export function mergeCyclePair({ all, active }: CyclePair): CycleSummary[] {
  const mergedById = new Map<number, CycleSummary>();
  for (const cycle of all) {
    mergedById.set(cycle.id, cycle);
  }
  for (const activeCycle of active) {
    if (!mergedById.has(activeCycle.id)) {
      mergedById.set(activeCycle.id, activeCycle);
    }
  }
  return [...mergedById.values()].sort((left, right) => right.id - left.id);
}

/**
 * Read the merged cycle list the shell renders. This is the entry point every
 * cycle-consuming hook uses, so they share one cached pair.
 */
export function readMergedCycles(
  username: string,
  options: { bypassCache?: boolean; ttlMs?: number } = {},
): Promise<CycleSummary[]> {
  return readCyclesPair(username, options).then(mergeCyclePair);
}
