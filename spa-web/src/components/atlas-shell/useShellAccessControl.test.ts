import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import useShellAccessControl from "@/components/atlas-shell/useShellAccessControl";
import { logoutSession, type AuditSummaryResponse, type AuthUser } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    logoutSession: vi.fn(),
  };
});

type HarnessProps = {
  authHydrated: boolean;
  user: AuthUser | null;
  isAdmin: boolean;
  mode: string;
  adminTab: string;
  adminAiHealth: Record<string, unknown> | null;
  adminPdfHealth: Record<string, unknown> | null;
  adminAuditSummary: AuditSummaryResponse | null;
};

const ACTIVE_USER: AuthUser = {
  id: 10,
  username: "atlas-user",
  display_name: "Atlas User",
  role: "admin",
  team_id: null,
  manager_id: null,
};

function renderAccessHook(initialProps: HarnessProps) {
  const routerReplace = vi.fn();
  const handleSidebarModeSelect = vi.fn();
  const loadAdminResources = vi.fn(async () => undefined);
  const loadAdminHealth = vi.fn(async () => undefined);
  const loadAdminAuditSummary = vi.fn(async () => undefined);
  const setUser = vi.fn();
  const clearSnapshot = vi.fn();

  const hook = renderHook(
    (props: HarnessProps) =>
      useShellAccessControl({
        authHydrated: props.authHydrated,
        user: props.user,
        isAdmin: props.isAdmin,
        mode: props.mode,
        adminTab: props.adminTab,
        adminAiHealth: props.adminAiHealth,
        adminPdfHealth: props.adminPdfHealth,
        adminAuditSummary: props.adminAuditSummary,
        routerReplace,
        handleSidebarModeSelect,
        loadAdminResources,
        loadAdminHealth,
        loadAdminAuditSummary,
        setUser,
        clearSnapshot,
      }),
    { initialProps },
  );

  return {
    ...hook,
    routerReplace,
    handleSidebarModeSelect,
    loadAdminResources,
    loadAdminHealth,
    loadAdminAuditSummary,
    setUser,
    clearSnapshot,
  };
}

describe("useShellAccessControl", () => {
  it("redirects hydrated anonymous users to login", async () => {
    const { routerReplace } = renderAccessHook({
      authHydrated: true,
      user: null,
      isAdmin: false,
      mode: "atlas",
      adminTab: "cycles",
      adminAiHealth: null,
      adminPdfHealth: null,
      adminAuditSummary: null,
    });

    await waitFor(() => {
      expect(routerReplace).toHaveBeenCalledWith(
        expect.stringContaining("/login?return_to="),
      );
    });
  });

  it("navigates non-admin users away from admin mode", async () => {
    const { handleSidebarModeSelect } = renderAccessHook({
      authHydrated: true,
      user: { ...ACTIVE_USER, role: "member" },
      isAdmin: false,
      mode: "admin",
      adminTab: "cycles",
      adminAiHealth: null,
      adminPdfHealth: null,
      adminAuditSummary: null,
    });

    await waitFor(() => {
      expect(handleSidebarModeSelect).toHaveBeenCalledWith("atlas");
    });
  });

  it("loads admin resources in admin mode", async () => {
    const { loadAdminResources } = renderAccessHook({
      authHydrated: true,
      user: ACTIVE_USER,
      isAdmin: true,
      mode: "admin",
      adminTab: "cycles",
      adminAiHealth: null,
      adminPdfHealth: null,
      adminAuditSummary: null,
    });

    await waitFor(() => {
      expect(loadAdminResources).toHaveBeenCalledWith(ACTIVE_USER);
    });
  });

  it("loads admin health when ai tab is active and health is missing", async () => {
    const { loadAdminHealth } = renderAccessHook({
      authHydrated: true,
      user: ACTIVE_USER,
      isAdmin: true,
      mode: "admin",
      adminTab: "ai",
      adminAiHealth: null,
      adminPdfHealth: { status: "ok" },
      adminAuditSummary: null,
    });

    await waitFor(() => {
      expect(loadAdminHealth).toHaveBeenCalledWith(ACTIVE_USER, false);
    });
  });

  it("does not reload admin health when both health payloads already exist", async () => {
    const { loadAdminHealth } = renderAccessHook({
      authHydrated: true,
      user: ACTIVE_USER,
      isAdmin: true,
      mode: "admin",
      adminTab: "ai",
      adminAiHealth: { status: "ok" },
      adminPdfHealth: { status: "ok" },
      adminAuditSummary: null,
    });

    await waitFor(() => {
      expect(loadAdminHealth).not.toHaveBeenCalled();
    });
  });

  it("clears session state and routes to login even if logout transport fails", async () => {
    vi.mocked(logoutSession).mockRejectedValueOnce(new Error("network"));
    const { result, setUser, clearSnapshot, routerReplace } = renderAccessHook({
      authHydrated: true,
      user: ACTIVE_USER,
      isAdmin: true,
      mode: "atlas",
      adminTab: "cycles",
      adminAiHealth: null,
      adminPdfHealth: null,
      adminAuditSummary: null,
    });

    act(() => {
      result.current.handleSignOut();
    });

    await waitFor(() => {
      expect(setUser).toHaveBeenCalledWith(null);
      expect(clearSnapshot).toHaveBeenCalled();
      expect(routerReplace).toHaveBeenCalledWith("/login?return_to=%2F");
    });
  });

  it("loads audit summary when audit tab is active", async () => {
    const { loadAdminAuditSummary } = renderAccessHook({
      authHydrated: true,
      user: ACTIVE_USER,
      isAdmin: true,
      mode: "admin",
      adminTab: "audit",
      adminAiHealth: null,
      adminPdfHealth: null,
      adminAuditSummary: null,
    });

    await waitFor(() => {
      expect(loadAdminAuditSummary).toHaveBeenCalledWith(ACTIVE_USER);
    });
  });
});
