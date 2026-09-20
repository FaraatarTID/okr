import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { AuthUser, CycleSummary } from "@/lib/api";
import * as cyclesModule from "@/lib/cycles";
import useCyclesSource from "@/components/atlas-shell/useCyclesSource";

/**
 * These tests own the hook's contract, not the cache's.
 *
 * `readMergedCycles` is mocked at the module boundary on purpose. An earlier
 * version of this file drove the real cycle cache with a mocked `@/lib/api` and
 * was not deterministic: the cache is module state, so a payload from one test
 * was served to another (`expected [ 5, 4 ] to deeply equal [ 12, 11, 9, 2 ]`).
 * The cache itself — TTL expiry, in-flight joining, invalidation, clear, and the
 * refusal to cache failures — is covered directly and deterministically in
 * `src/lib/resourceCache.test.ts`.
 */
vi.mock("@/lib/cycles", () => ({
  readMergedCycles: vi.fn(),
}));

const baseUser: AuthUser = {
  id: 1,
  username: "alice",
  display_name: "Alice",
  role: "admin",
};

const cycle = (id: number, isActive = false): CycleSummary => ({
  id,
  title: `Cycle ${id}`,
  is_active: isActive,
  start_date: null,
  end_date: null,
});

const readMergedCyclesMock = () => vi.mocked(cyclesModule.readMergedCycles);

/**
 * Render the hook and hand back the `refreshCycles` callback plus a helper that
 * invokes it inside `act`. The callback is captured once, the way the real shell
 * does when it destructures the hook result, so a re-render between calls cannot
 * leave the test holding a stale reference.
 */
function setup() {
  const setSessionCycles = vi.fn();
  const { result } = renderHook(() =>
    useCyclesSource({ user: baseUser, setSessionCycles }),
  );
  const refresh = result.current.refreshCycles;

  const run = async (options?: { bypassCache?: boolean }): Promise<CycleSummary[]> => {
    let value: CycleSummary[] = [];
    await act(async () => {
      value = await refresh(baseUser, options);
    });
    return value;
  };

  return {
    setSessionCycles,
    refresh,
    run,
    pending: () => result.current.pending,
  };
}

describe("useCyclesSource", () => {
  beforeEach(() => {
    readMergedCyclesMock().mockReset();
  });

  it("returns the merged list and publishes it to session cycles", async () => {
    const merged = [cycle(12, true), cycle(11), cycle(9), cycle(2)];
    readMergedCyclesMock().mockResolvedValue(merged);
    const { run, setSessionCycles, pending } = setup();

    const value = await run();

    expect(value).toEqual(merged);
    expect(setSessionCycles).toHaveBeenCalledWith(merged);
    expect(pending()).toBe(false);
  });

  it("reads through the shared cycle cache for the acting user", async () => {
    readMergedCyclesMock().mockResolvedValue([]);
    const { run } = setup();

    await run();

    expect(readMergedCyclesMock()).toHaveBeenCalledWith("alice", {
      bypassCache: undefined,
    });
  });

  it("asks the cache to bypass when the caller requires fresh data", async () => {
    readMergedCyclesMock().mockResolvedValue([]);
    const { run } = setup();

    await run({ bypassCache: true });

    expect(readMergedCyclesMock()).toHaveBeenCalledWith("alice", {
      bypassCache: true,
    });
  });

  it("propagates a read failure and leaves session cycles untouched", async () => {
    readMergedCyclesMock().mockRejectedValue(new Error("cycles unavailable"));
    const { refresh, setSessionCycles, pending } = setup();

    await act(async () => {
      await expect(refresh(baseUser)).rejects.toThrow("cycles unavailable");
    });

    expect(setSessionCycles).not.toHaveBeenCalled();
    expect(pending()).toBe(false);
  });

  it("retries the cache on a later read instead of remembering the failure", async () => {
    readMergedCyclesMock().mockRejectedValueOnce(new Error("transient"));
    readMergedCyclesMock().mockResolvedValueOnce([cycle(3)]);
    const { run } = setup();

    await expect(
      act(async () => {
        await expect(run()).rejects.toThrow("transient");
      }),
    ).resolves.toBeUndefined();

    const recovered = await run();
    expect(recovered.map((row) => row.id)).toEqual([3]);
  });

  it("clears the pending flag even when the read fails", async () => {
    readMergedCyclesMock().mockRejectedValue(new Error("boom"));
    const { refresh, pending } = setup();

    await act(async () => {
      await expect(refresh(baseUser)).rejects.toThrow("boom");
    });

    expect(pending()).toBe(false);
  });
});
