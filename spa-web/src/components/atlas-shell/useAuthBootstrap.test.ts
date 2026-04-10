import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "@/lib/api";
import useAuthBootstrap from "@/components/atlas-shell/useAuthBootstrap";

vi.mock("@/lib/api", () => ({
  readSessionUser: vi.fn(),
  readSpaRolloutConfig: vi.fn(),
}));

describe("useAuthBootstrap", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
  });

  it("hydrates session user and rollout config", async () => {
    const readSessionUserMock = vi.mocked(api.readSessionUser);
    const readSpaRolloutConfigMock = vi.mocked(api.readSpaRolloutConfig);
    readSessionUserMock.mockResolvedValue({
      id: 7,
      username: "alice",
      display_name: "Alice",
      role: "admin",
    } as never);
    readSpaRolloutConfigMock.mockResolvedValue({
      enabled: true,
      allow_admins: true,
      allow_managers: true,
      allow_members: true,
      preview_bypass_enabled: true,
    } as never);

    const { result } = renderHook(() => useAuthBootstrap());

    await waitFor(() => {
      expect(result.current.authHydrated).toBe(true);
      expect(result.current.user?.username).toBe("alice");
      expect(result.current.rolloutConfig?.enabled).toBe(true);
    });
  });

  it("falls back to anonymous when session user read fails", async () => {
    const readSessionUserMock = vi.mocked(api.readSessionUser);
    readSessionUserMock.mockRejectedValue(new Error("unauthorized"));

    const { result } = renderHook(() => useAuthBootstrap());

    await waitFor(() => {
      expect(result.current.authHydrated).toBe(true);
      expect(result.current.user).toBeNull();
    });
  });
});
