import { describe, expect, it } from "vitest";

import type { AuthUser, CycleSummary } from "@/lib/api";
import { mergeCyclePair } from "@/lib/cycles";
import { cacheKeys, clearResourceCache, readThroughCache } from "@/lib/resourceCache";

/**
 * `mergeCyclePair` is pure, so it is tested directly with no mocking.
 *
 * The de-duplication C1 exists for — the deep-link bootstrap and the top-bar
 * cycle source each requesting the same `cycles.all` + `cycles.active` pair —
 * rests on `readThroughCache` joining concurrent readers of one key. That join is
 * proven on the real primitive in `src/lib/resourceCache.test.ts`, and re-proven
 * here against the exact keys `cycles.ts` uses, with a synthetic loader so no API
 * or network is involved. The hook-level tests mock `@/lib/cycles`, so no test
 * drives the real cycle cache through the API layer.
 */

const cycle = (id: number, isActive = false): CycleSummary => ({
  id,
  title: `Cycle ${id}`,
  is_active: isActive,
  start_date: null,
  end_date: null,
});

describe("mergeCyclePair", () => {
  it("guarantees every active cycle appears and orders by descending id", () => {
    const merged = mergeCyclePair({
      all: [cycle(2), cycle(9)],
      active: [cycle(12, true), cycle(9, true)],
    });

    expect(merged.map((row) => row.id)).toEqual([12, 9, 2]);
  });

  it("keeps the cycles.all entry when an id appears in both", () => {
    const fromAll = { ...cycle(9, false), title: "From all" };
    const fromActive = { ...cycle(9, true), title: "From active" };

    const merged = mergeCyclePair({ all: [fromAll], active: [fromActive] });

    expect(merged).toHaveLength(1);
    expect(merged[0].title).toBe("From all");
  });

  it("handles an empty pair", () => {
    expect(mergeCyclePair({ all: [], active: [] })).toEqual([]);
  });

  it("includes an active cycle that cycles.all omitted", () => {
    const merged = mergeCyclePair({ all: [], active: [cycle(12, true)] });
    expect(merged.map((row) => row.id)).toEqual([12]);
  });
});

describe("cycle cache keys", () => {
  const user = (username: string): AuthUser => ({
    id: 1,
    username,
    display_name: "User",
    role: "admin",
  });

  it("joins two concurrent consumers of the same user into one request", async () => {
    clearResourceCache();
    const key = cacheKeys.cycles(user("dedupe-user").username);
    let calls = 0;
    const loader = async () => {
      calls += 1;
      await new Promise((resolve) => setTimeout(resolve, 0));
      return "pair";
    };

    // Two independent consumers mounting together.
    const [first, second] = await Promise.all([
      readThroughCache(key, loader),
      readThroughCache(key, loader),
    ]);

    expect(first).toBe("pair");
    expect(second).toBe("pair");
    expect(calls).toBe(1);
    clearResourceCache();
  });

  it("keys by username so two users never share a cached pair", async () => {
    clearResourceCache();
    let calls = 0;
    const loader = async () => {
      calls += 1;
      return "pair";
    };

    await readThroughCache(cacheKeys.cycles("user-a"), loader);
    await readThroughCache(cacheKeys.cycles("user-b"), loader);

    expect(calls).toBe(2);
    clearResourceCache();
  });
});
