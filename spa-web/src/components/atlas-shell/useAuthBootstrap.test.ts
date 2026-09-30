import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import useAuthBootstrap from "./useAuthBootstrap";
import * as api from "@/lib/api";
import useShellAccessControl from "@/components/atlas-shell/useShellAccessControl";
import { SessionAuthError } from "@/lib/api/auth";

vi.mock("@/lib/api", async () => ({
  ...(await vi.importActual<typeof import("@/lib/api")>("@/lib/api")),
  readSessionUser: vi.fn(),
}));

describe("useAuthBootstrap", () => {
  const admin: api.AuthUser = { id: 1, username: "alice", display_name: "Alice", role: "admin", manager_id: null };
  const member: api.AuthUser = { ...admin, role: "member" };

  beforeEach(() => { vi.mocked(api.readSessionUser).mockReset(); });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  const settle = async () => { await act(async () => { await Promise.resolve(); }); };

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

  it("sets user to null on explicit session rejection", async () => {
    vi.mocked(api.readSessionUser).mockRejectedValue(new SessionAuthError(401, "no session"));
    const { result } = renderHook(() => useAuthBootstrap());
    await waitFor(() => {
      expect(result.current.authHydrated).toBe(true);
    });
    expect(result.current.user).toBeNull();
  });


  it("keeps the same user object when the periodic session check returns identical data", async () => {
    vi.useFakeTimers();
    vi.mocked(api.readSessionUser).mockImplementation(async () => ({ ...admin }));
    const { result } = renderHook(() => useAuthBootstrap());
    await settle();
    const first = result.current.user;
    expect(first?.username).toBe("alice");

    await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
    expect(vi.mocked(api.readSessionUser).mock.calls.length).toBeGreaterThan(1);
    expect(result.current.user).toBe(first);
  });

  it("replaces the user object when a field such as role actually changes", async () => {
    vi.useFakeTimers();
    vi.mocked(api.readSessionUser).mockResolvedValueOnce({ ...admin }).mockResolvedValue({ ...member });
    const { result } = renderHook(() => useAuthBootstrap());
    await settle();
    const first = result.current.user;

    await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
    expect(result.current.user).not.toBe(first);
    expect(result.current.user?.role).toBe("member");
  });  it("keeps the access gate pending after an initial transient failure until retry succeeds", async () => {
    vi.useFakeTimers();
    vi.mocked(api.readSessionUser).mockRejectedValueOnce(new Error("unavailable"))
      .mockResolvedValueOnce(admin);
    const { result } = renderHook(() => useAuthBootstrap());
    await settle();
    expect(result.current.authHydrated).toBe(false);
    expect(result.current.user).toBeNull();
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
    expect(result.current.authHydrated).toBe(true);
    expect(result.current.user?.role).toBe("admin");
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
    expect(gate).toHaveBeenCalledWith("/");
    expect(readSessionUserMock.mock.calls.length).toBeGreaterThan(readsAfterFirstMount);
  });

  it("updates the still-mounted admin gate after scheduled demotion and promotion", async () => {
    vi.useFakeTimers();
    const read = vi.mocked(api.readSessionUser);
    read.mockResolvedValueOnce(admin).mockResolvedValueOnce(member).mockResolvedValueOnce(admin);
    const gate = vi.fn();
    const { result, rerender } = renderHook(({ mode }: { mode: string }) => {
      const auth = useAuthBootstrap();
      const access = useShellAccessControl({
        authHydrated: auth.authHydrated, user: auth.user,
        isAdmin: auth.user?.role === "admin", isManager: false,
        mode, adminTab: "cycles", setAdminTab: vi.fn(),
        adminAiHealth: null, adminPdfHealth: null, adminAuditSummary: null,
        routerReplace: gate,
        loadAdminResources: vi.fn(async () => undefined),
        loadAdminHealth: vi.fn(async () => undefined),
        loadAdminAuditSummary: vi.fn(async () => undefined),
        setUser: auth.setUser, clearSnapshot: vi.fn(),
      });
      return { ...auth, ...access };
    }, { initialProps: { mode: "admin" } });
    await settle();
    expect(result.current.accessReady).toBe(true);
    rerender({ mode: "atlas" });
    rerender({ mode: "admin" });
    expect(read).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
    expect(result.current.user?.role).toBe("member");
    expect(result.current.accessReady).toBe(false);
    expect(gate).toHaveBeenCalledWith("/");
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
    expect(result.current.user?.role).toBe("admin");
    expect(result.current.accessReady).toBe(true);
  });

  it("revalidates only each visible minute and coalesces focus with visibility return", async () => {
    vi.useFakeTimers();
    Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" });
    const read = vi.mocked(api.readSessionUser).mockResolvedValue(admin);
    renderHook(() => useAuthBootstrap());
    await settle();
    await act(async () => { await vi.advanceTimersByTimeAsync(59_999); });
    expect(read).toHaveBeenCalledTimes(1);
    Object.defineProperty(document, "visibilityState", { configurable: true, value: "hidden" });
    await act(async () => { await vi.advanceTimersByTimeAsync(60_001); });
    expect(read).toHaveBeenCalledTimes(1);
    Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" });
    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
      await Promise.resolve();
      window.dispatchEvent(new Event("focus"));
      await Promise.resolve();
    });
    expect(read).toHaveBeenCalledTimes(2);
  });

  it("keeps one request in flight and preserves the user after a transient failure", async () => {
    vi.useFakeTimers();
    const read = vi.mocked(api.readSessionUser);
    let rejectRefresh!: (error: Error) => void;
    read.mockResolvedValueOnce(admin).mockImplementationOnce(() => new Promise((_, reject) => { rejectRefresh = reject; }))
      .mockResolvedValue(member);
    const { result } = renderHook(() => useAuthBootstrap());
    await settle();
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
    expect(read).toHaveBeenCalledTimes(2);
    await act(async () => {
      window.dispatchEvent(new Event("focus"));
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(read).toHaveBeenCalledTimes(2);
    await act(async () => { rejectRefresh(new Error("network failed")); await Promise.resolve(); });
    expect(result.current.user?.role).toBe("admin");
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
    expect(result.current.user?.role).toBe("member");
  });

  it("clears the user after an explicit auth rejection", async () => {
    vi.useFakeTimers();
    vi.mocked(api.readSessionUser).mockResolvedValueOnce(admin)
      .mockRejectedValueOnce(new SessionAuthError(401, "Unauthorized"));
    const { result } = renderHook(() => useAuthBootstrap());
    await settle();
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
    expect(result.current.user).toBeNull();
  });

  it("removes refresh timers and foreground listeners on unmount", async () => {
    vi.useFakeTimers();
    const read = vi.mocked(api.readSessionUser).mockResolvedValue(admin);
    const { unmount } = renderHook(() => useAuthBootstrap());
    await settle();
    unmount();
    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
      window.dispatchEvent(new Event("focus"));
      await vi.advanceTimersByTimeAsync(120_000);
    });
    expect(read).toHaveBeenCalledTimes(1);
  });
});
