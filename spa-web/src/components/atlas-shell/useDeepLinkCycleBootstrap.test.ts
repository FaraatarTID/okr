import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "@/lib/api";
import * as deeplink from "@/lib/deeplink";
import type { AuthUser, CycleSummary } from "@/lib/api";
import useDeepLinkCycleBootstrap from "@/components/atlas-shell/useDeepLinkCycleBootstrap";

const pathnameHolder = vi.hoisted(() => ({ value: "/" }));

vi.mock("next/navigation", () => ({
  usePathname: () => pathnameHolder.value,
}));

vi.mock("@/lib/api", () => ({
  readCyclesQuery: vi.fn(),
}));

vi.mock("@/lib/deeplink", async () => {
  const actual = await vi.importActual<typeof import("@/lib/deeplink")>("@/lib/deeplink");
  return {
    ...actual,
    parseDeepLink: vi.fn(actual.parseDeepLink),
  };
});

const baseUser: AuthUser = {
  id: 1,
  username: "alice",
  display_name: "Alice",
  role: "member",
};

function createSetters() {
  return {
    setResolvedCycle: vi.fn(),
    setCycleResolvePending: vi.fn(),
    setCycleResolveError: vi.fn(),
    setSessionCycles: vi.fn(),
    setCycleId: vi.fn(),
    setMode: vi.fn(),
    setLens: vi.fn(),
    setSelectedRef: vi.fn(),
    setFocusTaskRef: vi.fn(),
    setDeepLinkReady: vi.fn(),
  };
}

describe("useDeepLinkCycleBootstrap", () => {
  beforeEach(() => {
    // NOTE: do NOT call vi.restoreAllMocks() here — it would strip the
    // implementation from the parseDeepLink wrapper below, making it return
    // undefined in tests that rely on the real parser. clearAllMocks only
    // clears call history and keeps implementations intact.
    vi.clearAllMocks();
    window.history.replaceState(null, "", "/");
    pathnameHolder.value = "/";
  });

  it("syncs state from deep-link query", async () => {
    window.history.replaceState(
      null,
      "",
      "/?cycle=8&mode=timeline&lens=owner&sel=task_3&ft=task_4",
    );
    const setters = createSetters();
    vi.mocked(deeplink.parseDeepLink).mockReturnValue({
      cycle: "8",
      mode: "timeline",
      lens: "owner",
      sel: "task_3",
      ft: "task_4",
    });

    renderHook(() =>
      useDeepLinkCycleBootstrap({
        user: null,
        canManageCycleSelection: true,
        parsedCycleId: null,
        resolvedCycle: null,
        sessionCycles: [],
        deepLinkReady: false,
        deepLinkQuery: "",
        ...setters,
      }),
    );
    act(() => {
      window.dispatchEvent(new PopStateEvent("popstate"));
    });

    await waitFor(() => {
      expect(setters.setCycleId).toHaveBeenCalledWith("8");
      expect(setters.setMode).toHaveBeenCalledWith("timeline");
      expect(setters.setLens).toHaveBeenCalledWith("owner");
      expect(setters.setSelectedRef).toHaveBeenCalledWith("task_3");
      expect(setters.setFocusTaskRef).toHaveBeenCalledWith("task_4");
      expect(setters.setDeepLinkReady).toHaveBeenCalledWith(true);
    }, { timeout: 2000 });
  });

  it("auto-selects active cycle when no cycle is present in deep link", async () => {
    const readCyclesQueryMock = vi.mocked(api.readCyclesQuery);
    // New behavior: cycles.all (dropdown list) and cycles.active are fetched
    // in parallel; the active cycle is authoritative for auto-selection.
    readCyclesQueryMock.mockImplementation(async ({ kind }: { kind: string }) =>
      kind === "cycles.active"
        ? ([
            { id: 12, title: "Q2", is_active: true, start_date: "2026-04-01", end_date: "2026-06-30" },
          ] as CycleSummary[])
        : ([
            { id: 12, title: "Q2", is_active: true, start_date: "2026-04-01", end_date: "2026-06-30" },
            { id: 11, title: "Q1", is_active: false, start_date: "2026-01-01", end_date: "2026-03-31" },
          ] as CycleSummary[]),
    );
    const setters = createSetters();

    renderHook(() =>
      useDeepLinkCycleBootstrap({
        user: baseUser,
        parsedCycleId: null,
        resolvedCycle: null,
        sessionCycles: [],
        deepLinkReady: true,
        deepLinkQuery: "",
        ...setters,
      }),
    );

    await waitFor(() => {
      expect(readCyclesQueryMock).toHaveBeenCalledWith({
        actor_username: "alice",
        kind: "cycles.all",
      });
      expect(readCyclesQueryMock).toHaveBeenCalledWith({
        actor_username: "alice",
        kind: "cycles.active",
      });
      expect(setters.setCycleId).toHaveBeenCalledWith("12");
      expect(setters.setResolvedCycle).toHaveBeenCalledWith(
        expect.objectContaining({ id: 12, title: "Q2" }),
      );
      expect(setters.setCycleResolvePending).toHaveBeenCalledWith(true);
      expect(setters.setCycleResolvePending).toHaveBeenLastCalledWith(false);
    });
  });

  it("prefers the manager-owned active cycle over the global active cycle", async () => {
    const readCyclesQueryMock = vi.mocked(api.readCyclesQuery);
    readCyclesQueryMock.mockImplementation(async ({ kind }: { kind: string }) =>
      kind === "cycles.active"
        ? ([
            { id: 1, title: "Global Q1", is_active: true, owner_manager_id: null },
            { id: 9, title: "Manager Q3", is_active: true, owner_manager_id: 1 },
          ] as CycleSummary[])
        : ([] as CycleSummary[]),
    );
    const setters = createSetters();

    renderHook(() =>
      useDeepLinkCycleBootstrap({
        user: { ...baseUser, role: "manager" },
        parsedCycleId: null,
        resolvedCycle: null,
        sessionCycles: [],
        deepLinkReady: true,
        deepLinkQuery: "",
        ...setters,
      }),
    );

    await waitFor(() => {
      expect(setters.setCycleId).toHaveBeenCalledWith("9");
      expect(setters.setResolvedCycle).toHaveBeenCalledWith(
        expect.objectContaining({ id: 9, title: "Manager Q3" }),
      );
    });
  });

  it("prefers the global active cycle for admins while retaining manager cycles", async () => {
    const readCyclesQueryMock = vi.mocked(api.readCyclesQuery);
    readCyclesQueryMock.mockImplementation(async ({ kind }: { kind: string }) =>
      kind === "cycles.active"
        ? ([
            { id: 9, title: "Manager Q3", is_active: true, owner_manager_id: 2 },
            { id: 3, title: "Global Q1", is_active: true, owner_manager_id: null },
          ] as CycleSummary[])
        : ([] as CycleSummary[]),
    );
    const setters = createSetters();

    renderHook(() =>
      useDeepLinkCycleBootstrap({
        user: { ...baseUser, role: "admin" },
        parsedCycleId: null,
        resolvedCycle: null,
        sessionCycles: [],
        deepLinkReady: true,
        deepLinkQuery: "",
        ...setters,
      }),
    );

    await waitFor(() => {
      expect(setters.setCycleId).toHaveBeenCalledWith("3");
      expect(setters.setResolvedCycle).toHaveBeenCalledWith(
        expect.objectContaining({ id: 3, title: "Global Q1" }),
      );
      expect(setters.setSessionCycles).toHaveBeenCalledWith(
        expect.arrayContaining([
          expect.objectContaining({ id: 9, owner_manager_id: 2 }),
          expect.objectContaining({ id: 3, owner_manager_id: null }),
        ]),
      );
    });
  });

  it("hydrates parsed cycle details from cycles.all when needed", async () => {
    const readCyclesQueryMock = vi.mocked(api.readCyclesQuery);
    readCyclesQueryMock.mockImplementation(async ({ kind }: { kind: string }) =>
      kind === "cycles.active"
        ? ([
            { id: 4, title: "Q2", is_active: true, start_date: "2026-04-01", end_date: "2026-06-30" },
          ] as CycleSummary[])
        : ([
            { id: 5, title: "Q3", is_active: false, start_date: "2026-07-01", end_date: "2026-09-30" },
            { id: 4, title: "Q2", is_active: true, start_date: "2026-04-01", end_date: "2026-06-30" },
          ] as CycleSummary[]),
    );
    const setters = createSetters();

    renderHook(() =>
      useDeepLinkCycleBootstrap({
        user: baseUser,
        parsedCycleId: 5,
        resolvedCycle: { id: 5, title: "" },
        sessionCycles: [],
        deepLinkReady: false,
        deepLinkQuery: "",
        ...setters,
      }),
    );

    await waitFor(() => {
      expect(readCyclesQueryMock).toHaveBeenCalledWith({
        actor_username: "alice",
        kind: "cycles.all",
      });
      expect(setters.setResolvedCycle).toHaveBeenCalledWith(
        expect.objectContaining({ id: 5, title: "Q3" }),
      );
      expect(setters.setSessionCycles).toHaveBeenCalled();
    });
    expect(
      readCyclesQueryMock.mock.calls.filter(([input]) => input.kind === "cycles.all"),
    ).toHaveLength(1);
  });

  // The three tests below fence C8. While every route rendered its own
  // <AtlasShell />, a navigation remounted the shell and the boot effect re-read
  // the path on that fresh mount. A shared layout keeps the shell mounted, so
  // the path must be re-read when it changes instead.

  it("derives the mode from the route when the query has no mode parameter", async () => {
    // Regression: an earlier draft wrote `modeForLocation(...) || parsed.mode ||
    // DEFAULT_MODE`. parseDeepLink().mode is always populated with DEFAULT_MODE,
    // so that fallback made the path unreachable and silently pinned every route
    // to "atlas". Booting /weekly with no mode parameter must yield "weekly".
    window.history.replaceState(null, "", "/weekly");
    pathnameHolder.value = "/weekly";
    const setters = createSetters();

    renderHook(() =>
      useDeepLinkCycleBootstrap({
        user: null,
        canManageCycleSelection: true,
        parsedCycleId: null,
        resolvedCycle: null,
        sessionCycles: [],
        deepLinkReady: false,
        deepLinkQuery: "",
        ...setters,
      }),
    );

    await waitFor(() => {
      expect(setters.setMode).toHaveBeenCalledWith("weekly");
    });
    // The most recent derivation must be the path's mode, not the default. Using
    // the call history here would be wrong: the boot sync may legitimately have
    // passed through the default before the path was known.
    expect(setters.setMode.mock.lastCall?.[0]).toBe("weekly");
  });

  it("re-derives the mode when the pathname changes without a remount", async () => {
    window.history.replaceState(null, "", "/weekly");
    pathnameHolder.value = "/weekly";
    const setters = createSetters();

    const { rerender } = renderHook(() =>
      useDeepLinkCycleBootstrap({
        user: null,
        canManageCycleSelection: true,
        parsedCycleId: null,
        resolvedCycle: null,
        sessionCycles: [],
        deepLinkReady: true,
        deepLinkQuery: "",
        ...setters,
      }),
    );

    await waitFor(() => {
      expect(setters.setMode).toHaveBeenCalledWith("weekly");
    });

    // Navigation: the URL changes but the component instance survives.
    act(() => {
      window.history.replaceState(null, "", "/timeline");
      pathnameHolder.value = "/timeline";
    });
    rerender();

    await waitFor(() => {
      expect(setters.setMode).toHaveBeenCalledWith("timeline");
    });

    // A mode parameter still outranks the path.
    act(() => {
      window.history.replaceState(null, "", "/timeline?mode=retrobox");
      pathnameHolder.value = "/admin";
    });
    rerender();

    await waitFor(() => {
      expect(setters.setMode).toHaveBeenCalledWith("retrobox");
    });
  });

  it("ignores an unknown mode parameter and falls back to the path", async () => {
    window.history.replaceState(null, "", "/daily?mode=not-a-mode");
    pathnameHolder.value = "/daily";
    const setters = createSetters();

    renderHook(() =>
      useDeepLinkCycleBootstrap({
        user: null,
        canManageCycleSelection: true,
        parsedCycleId: null,
        resolvedCycle: null,
        sessionCycles: [],
        deepLinkReady: true,
        deepLinkQuery: "",
        ...setters,
      }),
    );

    await waitFor(() => {
      expect(setters.setMode).toHaveBeenCalledWith("daily");
    });
  });
});
