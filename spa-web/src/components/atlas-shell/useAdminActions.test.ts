import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "@/lib/api";
import type { AuthUser, CycleSummary } from "@/lib/api";
import useAdminActions from "@/components/atlas-shell/useAdminActions";

vi.mock("@/lib/api", () => ({
  createCycleMutation: vi.fn(),
  createTeamMutation: vi.fn(),
  createUserMutation: vi.fn(),
  deleteCycleMutation: vi.fn(),
  deleteTeamMutation: vi.fn(),
  readAdminDbBackup: vi.fn(),
  resetUserPasswordMutation: vi.fn(),
  restoreAdminDbBackup: vi.fn(),
  updateCycleMutation: vi.fn(),
  updateTeamMutation: vi.fn(),
  updateUserMutation: vi.fn(),
}));

const baseUser: AuthUser = {
  id: 1,
  username: "alice",
  display_name: "Alice",
  role: "admin",
};

function renderAdminHook() {
  const loadAdminCycles = vi.fn().mockResolvedValue(undefined);
  const loadAdminUsersAndTeams = vi.fn().mockResolvedValue(undefined);
  const loadAdminResources = vi.fn().mockResolvedValue(undefined);
  const onCycleActivated = vi.fn();
  const setAdminCycleError = vi.fn();
  const setAdminDataError = vi.fn();

  const hook = renderHook(() =>
    useAdminActions({
      user: baseUser,
      isAdmin: true,
      adminUsers: [
        {
          id: 1,
          username: "alice",
          display_name: "Alice",
          role: "admin",
          is_active: true,
          must_change_password: false,
        },
      ],
      setAdminCycleError,
      setAdminDataError,
      loadAdminCycles,
      loadAdminUsersAndTeams,
      loadAdminResources,
      onCycleActivated,
      toIsoStart: (value) => `${value}T00:00:00Z`,
      toIsoEnd: (value) => `${value}T23:59:59Z`,
    }),
  );

  return {
    ...hook,
    loadAdminCycles,
    loadAdminUsersAndTeams,
    loadAdminResources,
    onCycleActivated,
    setAdminCycleError,
    setAdminDataError,
  };
}

describe("useAdminActions", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
  });

  it("validates required username and password when creating users", async () => {
    const createUserMutationMock = vi.mocked(api.createUserMutation);
    const { result, setAdminDataError } = renderAdminHook();

    await act(async () => {
      await result.current.handleAdminCreateUser();
    });

    expect(createUserMutationMock).not.toHaveBeenCalled();
    expect(setAdminDataError).toHaveBeenCalledWith("Username and password are required.");
  });

  it("creates user and refreshes users/teams data", async () => {
    const createUserMutationMock = vi.mocked(api.createUserMutation);
    createUserMutationMock.mockResolvedValue({ id: 10, username: "new-user" } as never);
    const { result, loadAdminUsersAndTeams } = renderAdminHook();

    act(() => {
      result.current.setAdminUserDraft((prev) => ({
        ...prev,
        username: "new-user",
        password: "pw-test",
        displayName: "New User",
      }));
    });

    await act(async () => {
      await result.current.handleAdminCreateUser();
    });

    expect(createUserMutationMock).toHaveBeenCalledWith(
      expect.objectContaining({
        actor_username: "alice",
        username: "new-user",
      }),
    );
    expect(loadAdminUsersAndTeams).toHaveBeenCalledWith(baseUser);
    expect(result.current.adminCycleMessage).toContain('User "new-user" created.');
  });

  it("restores backup when confirmation and file are provided", async () => {
    const restoreAdminDbBackupMock = vi.mocked(api.restoreAdminDbBackup);
    restoreAdminDbBackupMock.mockResolvedValue({
      success: true,
      restored_entities: 12,
      warnings: [],
    } as never);
    const { result, loadAdminResources } = renderAdminHook();

    const file = new File(
      [JSON.stringify({ users: [{ id: 1 }] })],
      "backup.json",
      { type: "application/json" },
    );
    act(() => {
      result.current.setAdminBackupFile(file);
      result.current.setAdminBackupConfirm("RESTORE");
    });

    await act(async () => {
      await result.current.handleAdminBackupRestore();
    });

    expect(restoreAdminDbBackupMock).toHaveBeenCalledWith(
      expect.objectContaining({ actor_username: "alice" }),
    );
    expect(loadAdminResources).toHaveBeenCalledWith(baseUser);
    expect(result.current.adminCycleMessage).toBe("Backup restored.");
  });

  it("activates cycle and forwards selected active cycle callback", async () => {
    const updateCycleMutationMock = vi.mocked(api.updateCycleMutation);
    updateCycleMutationMock.mockResolvedValue({ ok: true } as never);
    const { result, loadAdminCycles, onCycleActivated } = renderAdminHook();
    const cycle: CycleSummary = {
      id: 9,
      title: "Q2-2026",
      start_date: "2026-04-01",
      end_date: "2026-06-30",
      is_active: false,
    };

    await act(async () => {
      await result.current.handleAdminSetCycleActive(cycle, true);
    });

    expect(updateCycleMutationMock).toHaveBeenCalledWith(
      expect.objectContaining({
        actor_username: "alice",
        cycle_id: 9,
        is_active: true,
      }),
    );
    expect(loadAdminCycles).toHaveBeenCalledWith(baseUser);
    expect(onCycleActivated).toHaveBeenCalledWith(cycle);
  });

  it("validates password reset requires selected user and new password", async () => {
    const resetUserPasswordMutationMock = vi.mocked(api.resetUserPasswordMutation);
    const { result, setAdminDataError } = renderAdminHook();

    await act(async () => {
      await result.current.handleAdminResetPassword();
    });

    expect(resetUserPasswordMutationMock).not.toHaveBeenCalled();
    expect(setAdminDataError).toHaveBeenCalledWith("Select a user and enter a new password.");
  });

  it("resets password and shows user display name in message", async () => {
    const resetUserPasswordMutationMock = vi.mocked(api.resetUserPasswordMutation);
    resetUserPasswordMutationMock.mockResolvedValue({ ok: true } as never);
    const { result } = renderAdminHook();

    act(() => {
      result.current.setAdminResetDraft({
        userId: "1",
        newPassword: "pw-test",
        requireChange: true,
      });
    });

    await act(async () => {
      await result.current.handleAdminResetPassword();
    });

    expect(resetUserPasswordMutationMock).toHaveBeenCalledWith(
      expect.objectContaining({
        actor_username: "alice",
        user_id: 1,
        new_password: "pw-test",
        require_change: true,
      }),
    );
    expect(result.current.adminCycleMessage).toBe("Password reset for Alice.");
  });
});
