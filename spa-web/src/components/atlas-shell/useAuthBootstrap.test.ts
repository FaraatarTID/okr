import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import useAuthBootstrap from "./useAuthBootstrap";
import * as api from "@/lib/api";
import useShellAccessControl from "@/components/atlas-shell/useShellAccessControl";

vi.mock("@/lib/api", async () => ({
  ...(await vi.importActual<typeof import("@/lib/api")>("@/lib/api")),
  readSessionUser: vi.fn(),
}));

describe("useAuthBootstrap", () => {
  it("hydrates session user", async () => {
    const readSessionUserMock = vi.mocked(api.readSessionUser);
    readSessionUserMock.mockResolvedValue({
      username: "alice",
      display_name: "Alice",
      role: "admin",
      manager_id: null,
    } as api.AuthUser);

    const { result } = renderHook(() => useAuthBootstrap());
    await waitFor(() => {
      expect(result.current.authHydrated).toBe(true);
      expect(result.current.user?.username).toBe("alice");
    });
    expect(result.current.user?.username).toBe("alice");
  });

  it("sets user to null on session fetch failure", async () => {
    vi.mocked(api.readSessionUser).mockRejectedValue(new Error("no session"));
    const { result } = renderHook(() => useAuthBootstrap());
    await waitFor(() => {
      expect(result.current.authHydrated).toBe(true);
    });
    expect(result.current.user).toBeNull();
  });

  it("reads a fresh role on a new mount and applies that role to the admin gate", async () => {
    const readSessionUserMock = vi.mocked(api.readSessionUser);
    readSessionUserMock.mockResolvedValue({
      username: "alice",
      display_name: "Alice",
      role: "admin",
      manager_id: null,
    } as api.AuthUser);

    const gate = vi.fn();
    const renderFreshShell = () =>
      renderHook(() => {
        const auth = useAuthBootstrap();
        const user = auth.user;
        const access = useShellAccessControl({
          authHydrated: auth.authHydrated,
          user,
          isAdmin: user?.role === "admin",
          isManager: user?.role === "manager",
          mode: "admin",
          adminTab: "cycles",
          setAdminTab: vi.fn(),
          adminAiHealth: null,
          adminPdfHealth: null,
          adminAuditSummary: null,
          routerReplace: gate,
          handleSidebarModeSelect: gate,
          loadAdminResources: vi.fn(async () => undefined),
          loadAdminHealth: vi.fn(async () => undefined),
          loadAdminAuditSummary: vi.fn(async () => undefined),
          setUser: auth.setUser,
          clearSnapshot: vi.fn(),
        });
        return { ...auth, ...access };
      });

    const firstMount = renderFreshShell();
    await waitFor(() => expect(firstMount.result.current.accessReady).toBe(true));
    firstMount.unmount();
    const readsAfterFirstMount = readSessionUserMock.mock.calls.length;

    readSessionUserMock.mockResolvedValue({
      username: "alice",
      display_name: "Alice",
      role: "member",
      manager_id: null,
    } as api.AuthUser);
    const secondMount = renderFreshShell();
    await waitFor(() => expect(secondMount.result.current.user?.role).toBe("member"));
    expect(secondMount.result.current.user?.role).toBe("member");
    expect(secondMount.result.current.accessReady).toBe(false);
    expect(gate).toHaveBeenCalledWith("atlas");
    expect(readSessionUserMock.mock.calls.length).toBeGreaterThan(readsAfterFirstMount);
  });
});
