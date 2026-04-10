import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "@/lib/api";
import * as deeplink from "@/lib/deeplink";
import * as shellUiUtils from "@/components/atlas-shell/shellUiUtils";
import type { AuthUser, CycleSummary } from "@/lib/api";
import useDeepLinkCycleBootstrap from "@/components/atlas-shell/useDeepLinkCycleBootstrap";

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

vi.mock("@/components/atlas-shell/shellUiUtils", async () => {
  const actual = await vi.importActual<typeof import("@/components/atlas-shell/shellUiUtils")>(
    "@/components/atlas-shell/shellUiUtils",
  );
  return {
    ...actual,
    parsePreviewBypass: vi.fn(actual.parsePreviewBypass),
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
    setPreviewBypass: vi.fn(),
    setDeepLinkReady: vi.fn(),
  };
}

describe("useDeepLinkCycleBootstrap", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
    window.history.replaceState(null, "", "/");
  });

  it("syncs state from deep-link query", async () => {
    window.history.replaceState(
      null,
      "",
      "/?cycle=8&mode=timeline&lens=owner&sel=task_3&ft=task_4&spa_preview=1",
    );
    const setters = createSetters();
    vi.mocked(deeplink.parseDeepLink).mockReturnValue({
      cycle: "8",
      mode: "timeline",
      lens: "owner",
      sel: "task_3",
      ft: "task_4",
    });
    vi.mocked(shellUiUtils.parsePreviewBypass).mockReturnValue(true);

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
      expect(setters.setPreviewBypass).toHaveBeenCalledWith(true);
      expect(setters.setDeepLinkReady).toHaveBeenCalledWith(true);
    }, { timeout: 2000 });
  });

  it("auto-selects active cycle when no cycle is present in deep link", async () => {
    const readCyclesQueryMock = vi.mocked(api.readCyclesQuery);
    readCyclesQueryMock
      .mockResolvedValueOnce(
        [
          { id: 12, title: "Q2", is_active: true, start_date: "2026-04-01", end_date: "2026-06-30" },
          { id: 11, title: "Q1", is_active: false, start_date: "2026-01-01", end_date: "2026-03-31" },
        ] as CycleSummary[],
      )
      .mockResolvedValueOnce(
        [
          { id: 12, title: "Q2", is_active: true, start_date: "2026-04-01", end_date: "2026-06-30" },
        ] as CycleSummary[],
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

  it("hydrates parsed cycle details from cycles.all when needed", async () => {
    const readCyclesQueryMock = vi.mocked(api.readCyclesQuery);
    readCyclesQueryMock.mockResolvedValue([
      { id: 5, title: "Q3", is_active: false, start_date: "2026-07-01", end_date: "2026-09-30" },
      { id: 4, title: "Q2", is_active: true, start_date: "2026-04-01", end_date: "2026-06-30" },
    ] as CycleSummary[]);
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
  });
});
