"use client";

import { useEffect, useRef, type Dispatch, type SetStateAction } from "react";
import { usePathname } from "next/navigation";

import { type AuthUser, type CycleSummary } from "@/lib/api";
import { mergeCyclePair, readCyclesPair } from "@/lib/cycles";
import { DEFAULT_LENS, DEFAULT_MODE, normalizeFocusTaskRef, parseDeepLink } from "@/lib/deeplink";
import { modeForLocation } from "@/components/atlas-shell/navigation";

type ResolvedCycleState = Pick<
  CycleSummary,
  "id" | "title" | "start_date" | "end_date"
> & { is_active?: boolean };

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
  setDeepLinkReady,
}: UseDeepLinkCycleBootstrapInput) {
  const explicitCycleSelectionRef = useRef(false);
  const pathname = usePathname();

  useEffect(() => {
    if (parsedCycleId) {
      explicitCycleSelectionRef.current = true;
    }
  }, [parsedCycleId]);

  useEffect(() => {
    if (parsedCycleId) {
      setCycleResolveError("");
      if (!resolvedCycle || resolvedCycle.id !== parsedCycleId) {
        setResolvedCycle({ id: parsedCycleId, title: "" });
      }
    }
  }, [parsedCycleId, resolvedCycle, setCycleResolveError, setResolvedCycle]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const syncFromLocation = () => {
      const parsed = parseDeepLink(window.location.search);
      if (parsed.cycle && canManageCycleSelection) {
        setResolvedCycle(null);
        setCycleId(parsed.cycle);
      } else if (!canManageCycleSelection) {
        setCycleId("");
      }
      // Note: parseDeepLink().mode is always populated (normalizeMode returns
      // DEFAULT_MODE when the parameter is absent), so it must not be part of
      // this expression — an `|| parsed.mode` fallback would make modeForLocation
      // dead and silently pin every path to the default mode.
      setMode(modeForLocation(window.location.pathname, window.location.search));
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
    setResolvedCycle,
    setSelectedRef,
  ]);

  useEffect(() => {
    // Run when we have a logged‑in user. We deliberately ignore `deepLinkReady` here because we also need
    // to hydrate a parsed cycle ID even before the deep‑link state is marked ready (as exercised by the
    // hydration test).
    if (!user) {
      return;
    }
    let active = true;
    setCycleResolvePending(true);
    setCycleResolveError("");

    const pickCycle = (cycles: CycleSummary[]): CycleSummary | null => {
      if (!cycles.length) {
        return null;
      }
      const activeCycles = cycles.filter((cycle) => Boolean(cycle.is_active));
      const ownActiveCycle = activeCycles.find(
        (cycle) => cycle.owner_manager_id === user.id,
      );
      const globalActiveCycle = activeCycles.find(
        (cycle) => cycle.owner_manager_id == null,
      );
      const explicitActive =
        ownActiveCycle || (user.role === "admin" ? globalActiveCycle : null) || activeCycles[0];
      if (explicitActive) {
        return explicitActive;
      }
      return [...cycles].sort((left, right) => right.id - left.id)[0] || null;
    };

    void (async () => {
      try {
        // Fetch the complete list of cycles for the dropdown AND all visible
        // active cycles. Each owner may have one active cycle; admins prefer
        // their global cycle for automatic selection. The pair is read through
        // the shared cache, so `useCyclesSource` on the same mount joins this
        // request instead of issuing a duplicate one.
        const pair = await readCyclesPair(user.username);
        const { active: activeCycles } = pair;
        if (!active) {
          return;
        }
        // Merge: guarantee every active cycle is present in the dropdown even
        // if `cycles.all` was stale or scope-filtered it out.
        const merged = mergeCyclePair(pair);
        setSessionCycles(merged);

        // The authoritative active cycle (if any).
        const authoritativeActive = pickCycle(activeCycles.length ? activeCycles : merged);

        // If a specific cycle ID was parsed from the deep-link, hydrate its details from the full list.
        if (parsedCycleId) {
          const matched = merged.find((c) => c.id === parsedCycleId);
          if (matched) {
            setResolvedCycle({
              id: matched.id,
              title: matched.title,
              start_date: matched.start_date || null,
              end_date: matched.end_date || null,
              is_active: Boolean(matched.is_active),
            });
            setCycleId(String(matched.id));
            return;
          }
        }

        // When no explicit cycle ID is present *and* deep-link processing is
        // ready, select the scoped preferred active cycle.
        if (!parsedCycleId && deepLinkReady) {
          if (explicitCycleSelectionRef.current) {
            return;
          }
          const selectedActive = authoritativeActive;
          if (selectedActive) {
            setResolvedCycle({
              id: selectedActive.id,
              title: selectedActive.title,
              start_date: selectedActive.start_date || null,
              end_date: selectedActive.end_date || null,
              is_active: true,
            });
            setCycleId(String(selectedActive.id));
            return;
          }
          setCycleResolveError("No cycle found. Create or activate a cycle to load Atlas snapshot.");
          setResolvedCycle(null);
          return;
        }

        // If we have a parsedCycleId we already handled it above, and if deepLinkReady is false we don't
        // need to do anything further yet.
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

  useEffect(() => {
    // Re-derive the mode whenever the route changes. This is what makes the
    // single shared shell layout correct (C8).
    //
    // While every route rendered its own <AtlasShell />, a navigation remounted
    // the shell, and the boot effect above re-read the path on that fresh mount.
    // With one shared layout the shell stays mounted, so nothing re-reads the
    // path after the first navigation, and <Link>-style navigation — or any
    // future call to router.replace that does not also call setMode — would
    // leave the previous panel rendered at the new URL.
    //
    // Only the mode is reconciled here. Cycle, lens, and selection are handled by
    // the boot sync and by the explicit handlers, and re-deriving them on every
    // path change would fight those handlers.
    if (typeof window === "undefined") {
      return;
    }
    setMode(modeForLocation(pathname, window.location.search));
  }, [pathname, setMode]);
}
