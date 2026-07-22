"use client";

import { useCallback, useEffect, type Dispatch, type SetStateAction } from "react";

import {
  logoutSession,
  type AdminAiHealthResponse,
  type AuditSummaryResponse,
  type AdminPdfHealthResponse,
  type AuthUser,
} from "@/lib/api";

type UseShellAccessControlInput = {
  authHydrated: boolean;
  user: AuthUser | null;
  isAdmin: boolean;
  mode: string;
  adminTab: string;
  adminAiHealth: AdminAiHealthResponse | null;
  adminPdfHealth: AdminPdfHealthResponse | null;
  adminAuditSummary: AuditSummaryResponse | null;
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
  mode,
  adminTab,
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
    if (!authHydrated || user) {
      return;
    }
    const returnTo =
      typeof window === "undefined" ? "/" : `${window.location.pathname}${window.location.search}`;
    routerReplace(`/login?return_to=${encodeURIComponent(returnTo)}`);
  }, [authHydrated, routerReplace, user]);

  useEffect(() => {
    if (!user) {
      return;
    }
    if (!isAdmin && mode === "admin") {
      handleSidebarModeSelect("atlas");
    }
  }, [handleSidebarModeSelect, isAdmin, mode, user]);

  useEffect(() => {
    if (!user || !isAdmin || mode !== "admin") {
      return;
    }
    void loadAdminResources(user);
  }, [isAdmin, loadAdminResources, mode, user]);

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
