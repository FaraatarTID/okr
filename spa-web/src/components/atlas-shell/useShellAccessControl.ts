"use client";

import { useCallback, useEffect, type Dispatch, type SetStateAction } from "react";

import {
  forcedPasswordChangeLocation,
  logoutSession,
  type AdminAiHealthResponse,
  type AuditSummaryView,
  type AdminPdfHealthResponse,
  type AuthUser,
} from "@/lib/api";
import type { AdminTab } from "@/components/atlas-shell/AdminModePanel";
import { clearResourceCache } from "@/lib/resourceCache";

type UseShellAccessControlInput = {
  authHydrated: boolean;
  user: AuthUser | null;
  isAdmin: boolean;
  isManager: boolean;
  mode: string;
  adminTab: string;
  setAdminTab: Dispatch<SetStateAction<AdminTab>>;
  adminAiHealth: AdminAiHealthResponse | null;
  adminPdfHealth: AdminPdfHealthResponse | null;
  adminAuditSummary: AuditSummaryView | null;
  routerReplace: (href: string) => void;
  handleSidebarModeSelect: (nextMode: string) => void;
  loadAdminResources: (activeUser: AuthUser) => Promise<void>;
  loadAdminHealth: (activeUser: AuthUser, liveProbe: boolean) => Promise<void>;
  loadAdminAuditSummary: (activeUser: AuthUser) => Promise<void>;
  setUser: Dispatch<SetStateAction<AuthUser | null>>;
  clearSnapshot: () => void;
};

export default function useShellAccessControl({
  authHydrated,
  user,
  isAdmin,
  isManager,
  mode,
  adminTab,
  setAdminTab,
  adminAiHealth,
  adminPdfHealth,
  adminAuditSummary,
  routerReplace,
  handleSidebarModeSelect,
  loadAdminResources,
  loadAdminHealth,
  loadAdminAuditSummary,
  setUser,
  clearSnapshot,
}: UseShellAccessControlInput) {
  useEffect(() => {
    if (!authHydrated) {
      return;
    }
    const returnTo =
      typeof window === "undefined" ? "/" : `${window.location.pathname}${window.location.search}`;
    // A pending forced password change outranks everything else: it must be
    // enforced here, at the boundary every application route passes through, so
    // it cannot be bypassed by navigating straight to a route or by reloading
    // after login. Only the change flow may render while the flag is set.
    const destination = user
      ? forcedPasswordChangeLocation(user, returnTo)
      : `/login?return_to=${encodeURIComponent(returnTo)}`;
    routerReplace(destination);
  }, [authHydrated, routerReplace, user]);

  useEffect(() => {
    if (!user) {
      return;
    }
    // Managers may enter admin mode but are restricted to the cycles tab
    // (per-manager active cycles). Members are redirected out entirely.
    const canManageCycles = isAdmin || isManager;
    if (!canManageCycles && mode === "admin") {
      handleSidebarModeSelect("atlas");
      return;
    }
    if (!isAdmin && mode === "admin" && adminTab !== "cycles") {
      setAdminTab("cycles");
    }
    // `isManager` feeds `canManageCycles` above and was missing here. Today it
    // is masked, because `isManager` is derived from `user.role` and `user` is
    // in the list, so the effect already re-runs whenever the role changes.
    // Listed anyway: the sibling effects below include it, and the correctness
    // of the admin gate should not depend on how `isManager` happens to be
    // derived at the call site.
  }, [adminTab, handleSidebarModeSelect, isAdmin, isManager, mode, setAdminTab, user]);

  useEffect(() => {
    // Managers also need admin resources (users list feeds the cycle-owner
    // dropdown on their Cycles panel), so gate on canManageCycles, not isAdmin.
    const canManageCycles = isAdmin || isManager;
    if (!user || !canManageCycles || mode !== "admin") {
      return;
    }
    void loadAdminResources(user);
  }, [isAdmin, isManager, loadAdminResources, mode, user]);

  useEffect(() => {
    if (!user || !isAdmin || mode !== "admin" || adminTab !== "ai") {
      return;
    }
    if (adminAiHealth && adminPdfHealth) {
      return;
    }
    void loadAdminHealth(user, false);
  }, [adminAiHealth, adminPdfHealth, adminTab, isAdmin, loadAdminHealth, mode, user]);

  useEffect(() => {
    if (!user || !isAdmin || mode !== "admin" || adminTab !== "audit") {
      return;
    }
    if (adminAuditSummary) {
      return;
    }
    void loadAdminAuditSummary(user);
  }, [adminAuditSummary, adminTab, isAdmin, loadAdminAuditSummary, mode, user]);

  const handleSignOut = useCallback((): void => {
    void (async () => {
      try {
        await logoutSession();
      } catch {
        // Ignore logout transport errors and still clear local state.
      } finally {
        // Clear the read cache before dropping the user, so the next identity on
        // this browser can never be served the previous user's cycles or teams.
        clearResourceCache();
        setUser(null);
        clearSnapshot();
        routerReplace("/login?return_to=%2F");
      }
    })();
  }, [clearSnapshot, routerReplace, setUser]);

  return {
    handleSignOut,
  };
}
