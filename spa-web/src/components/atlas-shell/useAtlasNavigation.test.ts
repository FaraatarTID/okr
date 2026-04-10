import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import useAtlasNavigation from "@/components/atlas-shell/useAtlasNavigation";

describe("useAtlasNavigation", () => {
  it("navigates sidebar mode using deep-link query state", () => {
    const routerReplace = vi.fn();
    const setMode = vi.fn();
    const setSelectedRef = vi.fn();
    const setFocusTaskRef = vi.fn();

    const { result } = renderHook(() =>
      useAtlasNavigation({
        routerReplace,
        cycleId: "9",
        selectedRef: "task_7",
        focusTaskRef: "task_7",
        lens: "owner",
        setMode,
        setSelectedRef,
        setFocusTaskRef,
      }),
    );

    act(() => {
      result.current.handleSidebarModeSelect("timeline");
    });

    expect(routerReplace).toHaveBeenCalledWith(
      expect.stringContaining("/timeline?"),
    );
    expect(routerReplace).toHaveBeenCalledWith(
      expect.stringContaining("cycle=9"),
    );
    expect(routerReplace).toHaveBeenCalledWith(
      expect.stringContaining("mode=timeline"),
    );
    expect(setMode).toHaveBeenCalledWith("timeline");
    expect(setSelectedRef).not.toHaveBeenCalled();
    expect(setFocusTaskRef).not.toHaveBeenCalled();
  });

  it("opens timeline task in atlas and syncs selection state", () => {
    const routerReplace = vi.fn();
    const setMode = vi.fn();
    const setSelectedRef = vi.fn();
    const setFocusTaskRef = vi.fn();

    const { result } = renderHook(() =>
      useAtlasNavigation({
        routerReplace,
        cycleId: "12",
        selectedRef: "",
        focusTaskRef: "",
        lens: "focus",
        setMode,
        setSelectedRef,
        setFocusTaskRef,
      }),
    );

    act(() => {
      result.current.handleOpenTaskInAtlas(44);
    });

    expect(routerReplace).toHaveBeenCalledWith(
      expect.stringContaining("/?"),
    );
    expect(routerReplace).toHaveBeenCalledWith(
      expect.stringContaining("cycle=12"),
    );
    expect(routerReplace).toHaveBeenCalledWith(
      expect.stringContaining("sel=task_44"),
    );
    expect(routerReplace).toHaveBeenCalledWith(
      expect.stringContaining("ft=task_44"),
    );
    expect(setSelectedRef).toHaveBeenCalledWith("task_44");
    expect(setFocusTaskRef).toHaveBeenCalledWith("task_44");
    expect(setMode).toHaveBeenCalledWith("atlas");
  });
});
