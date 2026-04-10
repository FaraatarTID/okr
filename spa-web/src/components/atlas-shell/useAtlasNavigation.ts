"use client";

import { useCallback, type Dispatch, type SetStateAction } from "react";

import { buildDeepLinkQuery } from "@/lib/deeplink";
import { pathForMode } from "@/components/atlas-shell/navigation";

type UseAtlasNavigationInput = {
  routerReplace: (href: string) => void;
  cycleId: string;
  selectedRef: string;
  focusTaskRef: string;
  lens: string;
  setMode: Dispatch<SetStateAction<string>>;
  setSelectedRef: Dispatch<SetStateAction<string>>;
  setFocusTaskRef: Dispatch<SetStateAction<string>>;
};

export default function useAtlasNavigation({
  routerReplace,
  cycleId,
  selectedRef,
  focusTaskRef,
  lens,
  setMode,
  setSelectedRef,
  setFocusTaskRef,
}: UseAtlasNavigationInput) {
  const handleSidebarModeSelect = useCallback(
    (nextMode: string): void => {
      const routePath = pathForMode(nextMode);
      const query = buildDeepLinkQuery({
        cycle: cycleId,
        mode: nextMode,
        sel: selectedRef,
        ft: focusTaskRef,
        lens,
      });
      const nextUrl = query ? `${routePath}?${query}` : routePath;
      routerReplace(nextUrl);
      setMode(nextMode);
    },
    [cycleId, focusTaskRef, lens, routerReplace, selectedRef, setMode],
  );

  const handleOpenTaskInAtlas = useCallback(
    (taskId: number): void => {
      const ref = `task_${taskId}`;
      const routePath = pathForMode("atlas");
      const query = buildDeepLinkQuery({
        cycle: cycleId,
        mode: "atlas",
        sel: ref,
        ft: ref,
        lens,
      });
      routerReplace(query ? `${routePath}?${query}` : routePath);
      setSelectedRef(ref);
      setFocusTaskRef(ref);
      setMode("atlas");
    },
    [cycleId, lens, routerReplace, setFocusTaskRef, setMode, setSelectedRef],
  );

  return {
    handleSidebarModeSelect,
    handleOpenTaskInAtlas,
  };
}
