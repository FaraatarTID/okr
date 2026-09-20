import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "@/lib/api";
import type { AuthUser, CycleSummary } from "@/lib/api";
import useCyclesSource from "@/components/atlas-shell/useCyclesSource";
import { cacheKeys, clearResourceCache, invalidateCache } from "@/lib/resourceCache";

vi.mock("@/lib/api", () => ({
  readCyclesQuery: vi.fn(),
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

/** Resolve each query after a tick, so overlapping reads can genuinely overlap. */
function mockCycles(all: CycleSummary[], active: CycleSummary[]) {
  const readCyclesQueryMock = vi.mocked(api.readCyclesQuery);
  readCyclesQueryMock.mockImplementation(async ({ kind }: { kind: string }) => {
    await new Promise((resolve) => setTimeout(resolve, 0));
    return kind === "cycles.active" ? active : all;
  });
  return readCyclesQueryMock;
}

/**
 * Render the hook and hand back the `refreshCycles` callback plus a helper that
 * invokes it inside `act`. The callback is captured once, the way the real shell
 * does it when it destructures the hook result, so a re-render between calls
 * cannot leave the test holding a stale reference.
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
    vi.clearAllMocks();
    // The pair is cached per username and every test uses the same user.
    clearResourceCache();
  });

  it("merges cycles.all with cycles.active and orders by descending id", async () => {
    mockCycles([cycle(2), cycle(9), cycle(11)], [cycle(12, true)]);
    const { run, setSessionCycles, pending } = setup();

    const merged = await run();

    expect(merged.map((row) => row.id)).toEqual([12, 11, 9, 2]);
    expect(setSessionCycles).toHaveBeenCalledWith(merged);
    expect(pending()).toBe(false);
  });

  it("keeps the active cycle in the list even when cycles.all omits it", async () => {
    mockCycles([cycle(2)], [cycle(12, true)]);
    const { run } = setup();

    const merged = await run();

    expect(merged.map((row) => row.id)).toEqual([12, 2]);
  });

  it("issues the pair once when two reads overlap on the same mount", async () => {
    // The defect C1 fixes: the deep-link bootstrap and this hook both needed the
    // pair, and each issued its own request for it.
    const readCyclesQueryMock = mockCycles([cycle(1)], []);
    const { refresh } = setup();

    await act(async () => {
      await Promise.all([refresh(baseUser), refresh(baseUser)]);
    });

    expect(readCyclesQueryMock).toHaveBeenCalledTimes(2);
    expect(readCyclesQueryMock.mock.calls.map(([input]) => input.kind).sort()).toEqual([
      "cycles.active",
      "cycles.all",
    ]);
  });

  it("serves a later read within the TTL from cache", async () => {
    const readCyclesQueryMock = mockCycles([cycle(5)], []);
    const { run } = setup();

    await run();
    await run();

    expect(readCyclesQueryMock).toHaveBeenCalledTimes(2);
  });

  it("re-reads when the caller bypasses the cache", async () => {
    const readCyclesQueryMock = mockCycles([cycle(5)], []);
    const { run } = setup();

    await run();
    await run({ bypassCache: true });

    expect(readCyclesQueryMock).toHaveBeenCalledTimes(4);
  });

  it("propagates a cycles.all failure instead of caching it", async () => {
    const readCyclesQueryMock = vi.mocked(api.readCyclesQuery);
    readCyclesQueryMock.mockRejectedValue(new Error("cycles unavailable"));
    const { refresh, setSessionCycles, pending } = setup();

    await act(async () => {
      await expect(refresh(baseUser)).rejects.toThrow("cycles unavailable");
    });

    expect(pending()).toBe(false);
    expect(setSessionCycles).not.toHaveBeenCalled();

    // A transient failure must not be cached, so a retry reaches the API again.
    readCyclesQueryMock.mockClear();
    mockCycles([cycle(3)], []);
    await act(async () => {
      await refresh(baseUser);
    });
    expect(readCyclesQueryMock).toHaveBeenCalledTimes(2);
  });

  it("degrades to an empty active list when cycles.active fails", async () => {
    const readCyclesQueryMock = vi.mocked(api.readCyclesQuery);
    readCyclesQueryMock.mockImplementation(async ({ kind }: { kind: string }) => {
      if (kind === "cycles.active") {
        throw new Error("active unavailable");
      }
      return [cycle(4)];
    });
    const { run } = setup();

    const merged = await run();

    expect(merged.map((row) => row.id)).toEqual([4]);
  });

  it("re-reads after an explicit invalidation", async () => {
    const readCyclesQueryMock = mockCycles([cycle(5)], []);
    const { run } = setup();

    await run();
    invalidateCache(cacheKeys.cycles(baseUser.username));
    await run();

    expect(readCyclesQueryMock).toHaveBeenCalledTimes(4);
  });
});
