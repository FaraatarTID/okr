import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "@/lib/api";
import type { AuthUser } from "@/lib/api";
import useMindmapData from "@/components/atlas-shell/useMindmapData";

vi.mock("@/lib/api", () => ({
  readBackendQuery: vi.fn(),
}));

const baseUser: AuthUser = {
  id: 1,
  username: "alice",
  display_name: "Alice",
  role: "member",
};

describe("useMindmapData", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
  });

  it("clears payload when user or selected meta is missing", () => {
    const { result, rerender } = renderHook(
      ({ user, selectedMeta }) => useMindmapData({ user, selectedMeta }),
      {
        initialProps: { user: baseUser as AuthUser | null, selectedMeta: null as { id: number; type: "TASK" } | null },
      },
    );

    expect(result.current.mindmapPayload).toBeNull();
    rerender({ user: null, selectedMeta: { id: 7, type: "TASK" as const } });
    expect(result.current.mindmapPayload).toBeNull();
  });

  it("loads mindmap payload for selected node", async () => {
    const readBackendQueryMock = vi.mocked(api.readBackendQuery);
    readBackendQueryMock.mockResolvedValue({
      node: { id: 7, title: "Root" },
      node_type: "TASK",
    } as never);

    const { result } = renderHook(() =>
      useMindmapData({
        user: baseUser,
        selectedMeta: { id: 7, type: "TASK" },
      }),
    );

    await waitFor(() => {
      expect(readBackendQueryMock).toHaveBeenCalledWith(
        expect.objectContaining({
          actor_username: "alice",
          kind: "mindmap.root",
        }),
      );
    });
    await waitFor(() => {
      expect(result.current.mindmapPayload).toEqual(
        expect.objectContaining({
          node_type: "TASK",
        }),
      );
      expect(result.current.mindmapError).toBe("");
      expect(result.current.mindmapPending).toBe(false);
    });
  });

  it("sets error and clears payload when request fails", async () => {
    const readBackendQueryMock = vi.mocked(api.readBackendQuery);
    readBackendQueryMock.mockRejectedValue(new Error("mindmap unavailable"));

    const { result } = renderHook(() =>
      useMindmapData({
        user: baseUser,
        selectedMeta: { id: 11, type: "OBJECTIVE" },
      }),
    );

    await waitFor(() => {
      expect(result.current.mindmapError).toContain("mindmap unavailable");
      expect(result.current.mindmapPayload).toBeNull();
      expect(result.current.mindmapPending).toBe(false);
    });
  });
});
