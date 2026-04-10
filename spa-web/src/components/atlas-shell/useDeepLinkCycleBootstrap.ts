"use client";

import { useEffect, type Dispatch, type SetStateAction } from "react";

import { readCyclesQuery, type AuthUser, type CycleSummary } from "@/lib/api";
import { DEFAULT_LENS, DEFAULT_MODE, normalizeFocusTaskRef, parseDeepLink } from "@/lib/deeplink";
import { modeForPath } from "@/components/atlas-shell/navigation";
import {
  cyclePeriodLabel,
  parsePreviewBypass,
} from "@/components/atlas-shell/shellUiUtils";

type ResolvedCycleState = Pick<CycleSummary, "id" | "title" | "start_date" | "end_date">;

type UseDeepLinkCycleBootstrapInput = {
  user: AuthUser | null;
  canManageCycleSelection?: boolean;
  parsedCycleId: number | null;
  resolvedCycle: ResolvedCycleState | null;
  sessionCycles: CycleSummary[];
  deepLinkReady: boolean;
  deepLinkQuery: string;
  setResolvedCycle: Dispatch<SetStateAction<ResolvedCycleState | null>>;
  setCycleResolvePending: Dispatch<SetStateAction<boolean>>;
  setCycleResolveError: Dispatch<SetStateAction<string>>;
  setSessionCycles: Dispatch<SetStateAction<CycleSummary[]>>;
  setCycleId: Dispatch<SetStateAction<string>>;
  setMode: Dispatch<SetStateAction<string>>;
  setLens: Dispatch<SetStateAction<string>>;
  setSelectedRef: Dispatch<SetStateAction<string>>;
  setFocusTaskRef: Dispatch<SetStateAction<string>>;
  setPreviewBypass: Dispatch<SetStateAction<boolean>>;
  setDeepLinkReady: Dispatch<SetStateAction<boolean>>;
};

export default function useDeepLinkCycleBootstrap({
  user,
  canManageCycleSelection = true,
  parsedCycleId,
  resolvedCycle,
  sessionCycles,
  deepLinkReady,
  deepLinkQuery,
  setResolvedCycle,
  setCycleResolvePending,
  setCycleResolveError,
  setSessionCycles,
  setCycleId,
  setMode,
  setLens,
  setSelectedRef,
  setFocusTaskRef,
  setPreviewBypass,
  setDeepLinkReady,
}: UseDeepLinkCycleBootstrapInput) {
  useEffect(() => {
    if (parsedCycleId) {
      setCycleResolveError("");
      if (!resolvedCycle || resolvedCycle.id !== parsedCycleId) {
        setResolvedCycle({ id: parsedCycleId, title: "" });
      }
    }
  }, [parsedCycleId, resolvedCycle, setCycleResolveError, setResolvedCycle]);

  useEffect(() => {
    if (!user || !parsedCycleId) {
      return;
    }
    if (
      resolvedCycle &&
      resolvedCycle.id === parsedCycleId &&
      (Boolean(cyclePeriodLabel(resolvedCycle)) || Boolean(String(resolvedCycle.title || "").trim()))
    ) {
      return;
    }

    const cachedMatch = sessionCycles.find((cycle) => cycle.id === parsedCycleId);
    if (cachedMatch) {
      setResolvedCycle({
        id: cachedMatch.id,
        title: cachedMatch.title,
        start_date: cachedMatch.start_date || null,
        end_date: cachedMatch.end_date || null,
      });
      return;
    }

    let active = true;
    void (async () => {
      try {
        const cycles = await readCyclesQuery({
          actor_username: user.username,
          kind: "cycles.all",
        });
        if (!active) {
          return;
        }
        setSessionCycles([...cycles].sort((left, right) => right.id - left.id));
        const matched = cycles.find((cycle) => cycle.id === parsedCycleId);
        if (!matched) {
          return;
        }
        setResolvedCycle({
          id: matched.id,
          title: matched.title,
          start_date: matched.start_date || null,
          end_date: matched.end_date || null,
        });
      } catch {
        // keep current resolved cycle fallback
      }
    })();
    return () => {
      active = false;
    };
  }, [parsedCycleId, resolvedCycle, sessionCycles, setResolvedCycle, setSessionCycles, user]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const syncFromLocation = () => {
      const parsed = parseDeepLink(window.location.search);
      const pathMode = modeForPath(window.location.pathname);
      setPreviewBypass(parsePreviewBypass(window.location.search));
      if (parsed.cycle && canManageCycleSelection) {
        setResolvedCycle(null);
        setCycleId(parsed.cycle);
      } else if (!canManageCycleSelection) {
        setCycleId("");
      }
      setMode(parsed.mode || pathMode || DEFAULT_MODE);
      setLens(parsed.lens || DEFAULT_LENS);
      if (parsed.sel) {
        setSelectedRef(parsed.sel);
      }
      if (parsed.ft) {
        setFocusTaskRef(normalizeFocusTaskRef(parsed.ft));
      }
      setDeepLinkReady(true);
    };

    syncFromLocation();
    window.addEventListener("popstate", syncFromLocation);
    return () => {
      window.removeEventListener("popstate", syncFromLocation);
    };
  }, [
    canManageCycleSelection,
    setCycleId,
    setDeepLinkReady,
    setFocusTaskRef,
    setLens,
    setMode,
    setPreviewBypass,
    setResolvedCycle,
    setSelectedRef,
  ]);

  useEffect(() => {
    if (!user || !deepLinkReady || parsedCycleId) {
      return;
    }
    let active = true;
    setCycleResolvePending(true);
    setCycleResolveError("");

    const pickCycle = (cycles: CycleSummary[]): CycleSummary | null => {
      if (!cycles.length) {
        return null;
      }
      const explicitActive = cycles.find((cycle) => Boolean(cycle.is_active));
      if (explicitActive) {
        return explicitActive;
      }
      return [...cycles].sort((left, right) => right.id - left.id)[0] || null;
    };

    void (async () => {
      try {
        const activeCycles = await readCyclesQuery({
          actor_username: user.username,
          kind: "cycles.active",
        });
        if (!active) {
          return;
        }
        const sortedActive = [...activeCycles].sort((left, right) => right.id - left.id);
        const selectedActive = pickCycle(sortedActive);
        if (selectedActive) {
          setSessionCycles(sortedActive);
          setResolvedCycle({
            id: selectedActive.id,
            title: selectedActive.title,
            start_date: selectedActive.start_date || null,
            end_date: selectedActive.end_date || null,
          });
          setCycleId(String(selectedActive.id));
          void (async () => {
            try {
              const allCycles = await readCyclesQuery({
                actor_username: user.username,
                kind: "cycles.all",
              });
              if (!active) {
                return;
              }
              setSessionCycles([...allCycles].sort((left, right) => right.id - left.id));
            } catch {
              // keep active-cycle bootstrap state if full list hydration fails
            }
          })();
          return;
        }

        const cycles = await readCyclesQuery({
          actor_username: user.username,
          kind: "cycles.all",
        });
        if (!active) {
          return;
        }
        const sorted = [...cycles].sort((left, right) => right.id - left.id);
        setSessionCycles(sorted);
        const selected = pickCycle(sorted);
        if (!selected) {
          setCycleResolveError("No cycle found. Create or activate a cycle to load Atlas snapshot.");
          setResolvedCycle(null);
          return;
        }
        setResolvedCycle({
          id: selected.id,
          title: selected.title,
          start_date: selected.start_date || null,
          end_date: selected.end_date || null,
        });
        setCycleId(String(selected.id));
      } catch (error) {
        if (!active) {
          return;
        }
        setResolvedCycle(null);
        setCycleResolveError(
          `Could not auto-detect active cycle: ${String(error instanceof Error ? error.message : error)}`,
        );
      } finally {
        if (active) {
          setCycleResolvePending(false);
        }
      }
    })();

    return () => {
      active = false;
    };
  }, [
    deepLinkReady,
    parsedCycleId,
    setCycleId,
    setCycleResolveError,
    setCycleResolvePending,
    setResolvedCycle,
    setSessionCycles,
    user,
  ]);

  useEffect(() => {
    if (!deepLinkReady || typeof window === "undefined") {
      return;
    }
    const nextSearch = deepLinkQuery ? `?${deepLinkQuery}` : "";
    if (window.location.search === nextSearch) {
      return;
    }
    const nextUrl = `${window.location.pathname}${nextSearch}${window.location.hash}`;
    window.history.replaceState(null, "", nextUrl);
  }, [deepLinkQuery, deepLinkReady]);
}
