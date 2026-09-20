import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "@/lib/api";
import type { CycleSummary } from "@/lib/api";
import { mergeCyclePair, readCyclesPair, readMergedCycles } from "@/lib/cycles";
import { clearResourceCache } from "@/lib/resourceCache";

/**
 * The one test that exercises the real cache end to end.
 *
 * This is the assertion C1 exists for: the deep-link bootstrap and the top-bar
 * cycle source both needed the `cycles.all` + `cycles.active` pair, and each
 * issued its own request for it. The hook-level tests mock this module, so the
 * de-duplication has to be proven here, against the real cache.
 *
 * Every test uses its own username and clears the cache before and after itself,
 * so no other test file can observe or pollute this state.
 */
vi.mock("@/lib/api", () => ({
  readCyclesQuery: vi.fn(),
}));

const cycle = (id: number, isActive = false): CycleSummary => ({
  id,
  title: `Cycle ${id}`,
  is_active: isActive,
  start_date: null,
  end_date: null,
});

function mockQueries(all: CycleSummary[], active: CycleSummary[]) {
  const readCyclesQueryMock = vi.mocked(api.readCyclesQuery);
  readCyclesQueryMock.mockReset();
  readCyclesQueryMock.mockImplementation(async ({ kind }: { kind: string }) => {
    await new Promise((resolve) => setTimeout(resolve, 0));
    return kind === "cycles.active" ? active : all;
  });
  return readCyclesQueryMock;
}

describe("readCyclesPair", () => {
  beforeEach(() => {
    clearResourceCache();
  });

  it("issues the pair once when two consumers read together", async () => {
    const readCyclesQueryMock = mockQueries([cycle(2)], [cycle(12, true)]);

    // Two independent concurrent consumers, as two hooks on one mount are.
    await Promise.all([readCyclesPair("c1-concurrent"), readMergedCycles("c1-concurrent")]);

    expect(readCyclesQueryMock).toHaveBeenCalledTimes(2);
    expect(readCyclesQueryMock.mock.calls.map(([input]) => input.kind).sort()).toEqual([
      "cycles.active",
      "cycles.all",
    ]);
  });

  it("serves the second consumer from the cache within the TTL", async () => {
    const readCyclesQueryMock = mockQueries([cycle(2)], []);

    await readCyclesPair("c1-sequential");
    await readMergedCycles("c1-sequential");

    expect(readCyclesQueryMock).toHaveBeenCalledTimes(2);
    clearResourceCache();
  });

  it("bypasses the cache when the caller needs fresh data", async () => {
    const readCyclesQueryMock = mockQueries([cycle(2)], []);

    await readMergedCycles("c1-bypass");
    expect(readCyclesQueryMock).toHaveBeenCalledTimes(2);

    // Different data proves the second read really went back out.
    mockQueries([cycle(7)], []);
    const fresh = await readMergedCycles("c1-bypass", { bypassCache: true });

    expect(fresh.map((row) => row.id)).toEqual([7]);
    expect(readCyclesQueryMock).toHaveBeenCalledTimes(2);
    clearResourceCache();
  });

  it("keeps different users apart", async () => {
    const readCyclesQueryMock = mockQueries([cycle(2)], []);

    await readMergedCycles("c1-user-a");
    await readMergedCycles("c1-user-b");

    // Distinct keys, so no cross-user reuse.
    expect(readCyclesQueryMock).toHaveBeenCalledTimes(4);
    clearResourceCache();
  });

  it("degrades cycles.active to empty without failing the pair", async () => {
    const readCyclesQueryMock = vi.mocked(api.readCyclesQuery);
    readCyclesQueryMock.mockReset();
    readCyclesQueryMock.mockImplementation(async ({ kind }: { kind: string }) => {
      if (kind === "cycles.active") {
        throw new Error("active unavailable");
      }
      return [cycle(4)];
    });

    const pair = await readCyclesPair("c1-degrade");

    expect(pair.all.map((row) => row.id)).toEqual([4]);
    expect(pair.active).toEqual([]);
    clearResourceCache();
  });

  it("does not cache a cycles.all failure, so a retry reaches the API", async () => {
    const readCyclesQueryMock = vi.mocked(api.readCyclesQuery);
    readCyclesQueryMock.mockReset();
    readCyclesQueryMock.mockRejectedValue(new Error("down"));

    await expect(readCyclesPair("c1-retry")).rejects.toThrow("down");

    mockQueries([cycle(3)], []);
    const recovered = await readMergedCycles("c1-retry");

    expect(recovered.map((row) => row.id)).toEqual([3]);
    clearResourceCache();
  });
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
});
