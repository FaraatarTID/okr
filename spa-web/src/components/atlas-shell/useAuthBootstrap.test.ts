import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import useAuthBootstrap from "./useAuthBootstrap";
import * as api from "@/lib/api";

vi.mock("@/lib/api", () => ({
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
});
