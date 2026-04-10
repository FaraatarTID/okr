"use client";

import { useCallback, useState } from "react";

import {
  createCycleMutation,
  createTeamMutation,
  createUserMutation,
  deleteCycleMutation,
  deleteTeamMutation,
  readAdminDbBackup,
  resetUserPasswordMutation,
  restoreAdminDbBackup,
  updateCycleMutation,
  updateTeamMutation,
  updateUserMutation,
  type AdminDbRestoreResponse,
  type AuthUser,
  type CycleSummary,
  type TeamMutationResponse,
  type UserMutationResponse,
} from "@/lib/api";
import type {
  AdminCreateCycleDraft,
  AdminResetDraft,
  AdminTeamDraft,
  AdminUserDraft,
} from "@/components/atlas-shell/AdminModePanel";

type UseAdminActionsInput = {
  user: AuthUser | null;
  isAdmin: boolean;
  adminUsers: UserMutationResponse[];
  setAdminCycleError: (value: string) => void;
  setAdminDataError: (value: string) => void;
  loadAdminCycles: (activeUser: AuthUser) => Promise<void>;
  loadAdminUsersAndTeams: (activeUser: AuthUser) => Promise<void>;
  loadAdminResources: (activeUser: AuthUser) => Promise<void>;
  onCycleActivated: (cycle: CycleSummary) => void;
  toIsoStart: (dateValue: string) => string;
  toIsoEnd: (dateValue: string) => string;
};

type AdminUserRead = UserMutationResponse;
type AdminTeamRead = TeamMutationResponse;

export default function useAdminActions({
  user,
  isAdmin,
  adminUsers,
  setAdminCycleError,
  setAdminDataError,
  loadAdminCycles,
  loadAdminUsersAndTeams,
  loadAdminResources,
  onCycleActivated,
  toIsoStart,
  toIsoEnd,
}: UseAdminActionsInput) {
  const [adminCycleMessage, setAdminCycleMessage] = useState("");
  const [adminUserDraft, setAdminUserDraft] = useState<AdminUserDraft>({
    username: "",
    displayName: "",
    password: "",
    role: "member",
    managerId: "",
    teamId: "",
    mustChangePassword: true,
  });
  const [adminTeamDraft, setAdminTeamDraft] = useState<AdminTeamDraft>({
    name: "",
    description: "",
  });
  const [adminResetDraft, setAdminResetDraft] = useState<AdminResetDraft>({
    userId: "",
    newPassword: "",
    requireChange: false,
  });
  const [adminBackupFile, setAdminBackupFile] = useState<File | null>(null);
  const [adminBackupConfirm, setAdminBackupConfirm] = useState("");
  const [adminBackupRestoreResult, setAdminBackupRestoreResult] = useState<AdminDbRestoreResponse | null>(
    null,
  );
  const [adminBackupPending, setAdminBackupPending] = useState(false);
  const [adminCreateCycleDraft, setAdminCreateCycleDraft] = useState<AdminCreateCycleDraft>({
    title: "",
    startDate: "",
    endDate: "",
    isActive: false,
    ownerManagerId: "",
  });

  const handleAdminBackupExport = useCallback(async (): Promise<void> => {
    if (!user || !isAdmin) {
      return;
    }
    setAdminBackupPending(true);
    setAdminDataError("");
    try {
      const blob = await readAdminDbBackup({ actor_username: user.username });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      const stamp = new Date().toISOString().replace(/[:]/g, "-");
      anchor.href = url;
      anchor.download = `okr_backup_${stamp}.json`;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      URL.revokeObjectURL(url);
      setAdminCycleMessage("Backup downloaded.");
      setAdminBackupRestoreResult(null);
    } catch (error) {
      setAdminDataError(String(error instanceof Error ? error.message : error));
    } finally {
      setAdminBackupPending(false);
    }
  }, [isAdmin, user]);

  const handleAdminBackupRestore = useCallback(async (): Promise<void> => {
    if (!user || !isAdmin) {
      return;
    }
    if (!adminBackupFile) {
      setAdminDataError("Upload a backup JSON file first.");
      return;
    }
    if (adminBackupConfirm.trim() !== "RESTORE") {
      setAdminDataError('Type "RESTORE" to confirm.');
      return;
    }
    setAdminBackupPending(true);
    setAdminDataError("");
    try {
      const raw = await adminBackupFile.text();
      const payload = JSON.parse(raw) as Record<string, unknown>;
      const result = await restoreAdminDbBackup({
        actor_username: user.username,
        payload,
      });
      setAdminBackupRestoreResult(result);
      setAdminCycleMessage("Backup restored.");
      await loadAdminResources(user);
    } catch (error) {
      setAdminDataError(String(error instanceof Error ? error.message : error));
    } finally {
      setAdminBackupPending(false);
    }
  }, [adminBackupConfirm, adminBackupFile, isAdmin, loadAdminResources, user]);

  const handleAdminCreateUser = useCallback(async (): Promise<void> => {
    if (!user || !isAdmin) {
      return;
    }
    const username = adminUserDraft.username.trim();
    const password = adminUserDraft.password;
    if (!username || !password) {
      setAdminDataError("Username and password are required.");
      setAdminCycleMessage("");
      return;
    }
    try {
      const managerCandidate = Number.parseInt(adminUserDraft.managerId.trim(), 10);
      const teamCandidate = Number.parseInt(adminUserDraft.teamId.trim(), 10);
      await createUserMutation({
        actor_username: user.username,
        username,
        password,
        role: adminUserDraft.role,
        display_name: adminUserDraft.displayName.trim() || username,
        manager_id: Number.isFinite(managerCandidate) && managerCandidate > 0 ? managerCandidate : undefined,
        team_id: Number.isFinite(teamCandidate) && teamCandidate > 0 ? teamCandidate : undefined,
        must_change_password: adminUserDraft.mustChangePassword,
      });
      setAdminCycleMessage(`User "${username}" created.`);
      setAdminDataError("");
      setAdminUserDraft({
        username: "",
        displayName: "",
        password: "",
        role: "member",
        managerId: "",
        teamId: "",
        mustChangePassword: true,
      });
      await loadAdminUsersAndTeams(user);
    } catch (error) {
      setAdminDataError(String(error instanceof Error ? error.message : error));
    }
  }, [adminUserDraft, isAdmin, loadAdminUsersAndTeams, user]);

  const handleAdminToggleUserActive = useCallback(async (userRow: AdminUserRead): Promise<void> => {
    if (!user || !isAdmin) {
      return;
    }
    try {
      await updateUserMutation({
        actor_username: user.username,
        user_id: userRow.id,
        is_active: !userRow.is_active,
      });
      setAdminCycleMessage(
        `${userRow.username} ${userRow.is_active ? "deactivated" : "activated"}.`,
      );
      setAdminDataError("");
      await loadAdminUsersAndTeams(user);
    } catch (error) {
      setAdminDataError(String(error instanceof Error ? error.message : error));
    }
  }, [isAdmin, loadAdminUsersAndTeams, user]);

  const handleAdminCreateTeam = useCallback(async (): Promise<void> => {
    if (!user || !isAdmin) {
      return;
    }
    const teamName = adminTeamDraft.name.trim();
    if (!teamName) {
      setAdminDataError("Team name is required.");
      return;
    }
    try {
      await createTeamMutation({
        actor_username: user.username,
        name: teamName,
        description: adminTeamDraft.description.trim() || undefined,
      });
      setAdminCycleMessage(`Team "${teamName}" created.`);
      setAdminDataError("");
      setAdminTeamDraft({ name: "", description: "" });
      await loadAdminUsersAndTeams(user);
    } catch (error) {
      setAdminDataError(String(error instanceof Error ? error.message : error));
    }
  }, [adminTeamDraft.description, adminTeamDraft.name, isAdmin, loadAdminUsersAndTeams, user]);

  const handleAdminUpdateTeam = useCallback(async (team: AdminTeamRead): Promise<void> => {
    if (!user || !isAdmin) {
      return;
    }
    try {
      await updateTeamMutation({
        actor_username: user.username,
        team_id: team.id,
        name: team.name,
        description: team.description || undefined,
      });
      setAdminCycleMessage(`Team "${team.name}" updated.`);
      setAdminDataError("");
      await loadAdminUsersAndTeams(user);
    } catch (error) {
      setAdminDataError(String(error instanceof Error ? error.message : error));
    }
  }, [isAdmin, loadAdminUsersAndTeams, user]);

  const handleAdminDeleteTeam = useCallback(async (team: AdminTeamRead): Promise<void> => {
    if (!user || !isAdmin) {
      return;
    }
    if (typeof window !== "undefined") {
      const confirmed = window.confirm(`Delete team "${team.name}"?`);
      if (!confirmed) {
        return;
      }
    }
    try {
      await deleteTeamMutation({
        actor_username: user.username,
        team_id: team.id,
      });
      setAdminCycleMessage(`Team "${team.name}" deleted.`);
      setAdminDataError("");
      await loadAdminUsersAndTeams(user);
    } catch (error) {
      setAdminDataError(String(error instanceof Error ? error.message : error));
    }
  }, [isAdmin, loadAdminUsersAndTeams, user]);

  const handleAdminResetPassword = useCallback(async (): Promise<void> => {
    if (!user || !isAdmin) {
      return;
    }
    const userId = Number.parseInt(adminResetDraft.userId.trim(), 10);
    if (!Number.isFinite(userId) || userId <= 0 || !adminResetDraft.newPassword) {
      setAdminDataError("Select a user and enter a new password.");
      return;
    }
    try {
      const targetUser = adminUsers.find((row) => row.id === userId);
      const targetLabel = String(targetUser?.display_name || targetUser?.username || "").trim() || "selected user";
      await resetUserPasswordMutation({
        actor_username: user.username,
        user_id: userId,
        new_password: adminResetDraft.newPassword,
        require_change: adminResetDraft.requireChange,
      });
      setAdminCycleMessage(`Password reset for ${targetLabel}.`);
      setAdminDataError("");
      setAdminResetDraft({ userId: "", newPassword: "", requireChange: false });
    } catch (error) {
      setAdminDataError(String(error instanceof Error ? error.message : error));
    }
  }, [adminResetDraft, adminUsers, isAdmin, user]);

  const handleAdminCreateCycle = useCallback(async (): Promise<void> => {
    if (!user || !isAdmin) {
      return;
    }
    const title = adminCreateCycleDraft.title.trim();
    if (!title || !adminCreateCycleDraft.startDate || !adminCreateCycleDraft.endDate) {
      setAdminCycleError("Title, start date, and end date are required.");
      setAdminCycleMessage("");
      return;
    }
    const ownerManagerCandidate = Number.parseInt(adminCreateCycleDraft.ownerManagerId.trim(), 10);
    if (!Number.isFinite(ownerManagerCandidate) || ownerManagerCandidate <= 0) {
      setAdminCycleError("Select a cycle owner (manager/admin).");
      setAdminCycleMessage("");
      return;
    }
    setAdminCycleError("");
    setAdminCycleMessage("");
    try {
      await createCycleMutation({
        actor_username: user.username,
        title,
        start_date: toIsoStart(adminCreateCycleDraft.startDate),
        end_date: toIsoEnd(adminCreateCycleDraft.endDate),
        is_active: adminCreateCycleDraft.isActive,
        owner_manager_id: ownerManagerCandidate,
      });
      setAdminCycleMessage("Cycle created.");
      setAdminCreateCycleDraft({
        title: "",
        startDate: "",
        endDate: "",
        isActive: false,
        ownerManagerId: "",
      });
      await loadAdminCycles(user);
    } catch (error) {
      setAdminCycleError(String(error instanceof Error ? error.message : error));
    }
  }, [adminCreateCycleDraft, isAdmin, loadAdminCycles, toIsoEnd, toIsoStart, user]);

  const handleAdminSetCycleActive = useCallback(async (
    cycle: CycleSummary,
    isActive: boolean,
  ): Promise<void> => {
    if (!user || !isAdmin) {
      return;
    }
    setAdminCycleError("");
    setAdminCycleMessage("");
    try {
      await updateCycleMutation({
        actor_username: user.username,
        cycle_id: cycle.id,
        title: cycle.title,
        start_date: String(cycle.start_date || ""),
        end_date: String(cycle.end_date || ""),
        is_active: isActive,
        owner_manager_id:
          Number.isFinite(Number(cycle.owner_manager_id)) && Number(cycle.owner_manager_id) > 0
            ? Number(cycle.owner_manager_id)
            : undefined,
      });
      setAdminCycleMessage(isActive ? "Cycle activated." : "Cycle deactivated.");
      await loadAdminCycles(user);
      if (isActive) {
        onCycleActivated(cycle);
      }
    } catch (error) {
      setAdminCycleError(String(error instanceof Error ? error.message : error));
    }
  }, [isAdmin, loadAdminCycles, onCycleActivated, user]);

  const handleAdminDeleteCycle = useCallback(async (cycle: CycleSummary): Promise<void> => {
    if (!user || !isAdmin) {
      return;
    }
    if (typeof window !== "undefined") {
      const confirmed = window.confirm(`Delete cycle "${cycle.title}"? This cannot be undone.`);
      if (!confirmed) {
        return;
      }
    }
    setAdminCycleError("");
    setAdminCycleMessage("");
    try {
      await deleteCycleMutation({
        actor_username: user.username,
        cycle_id: cycle.id,
      });
      setAdminCycleMessage("Cycle deleted.");
      await loadAdminCycles(user);
    } catch (error) {
      setAdminCycleError(String(error instanceof Error ? error.message : error));
    }
  }, [isAdmin, loadAdminCycles, user]);

  const handleAdminUpdateCycleOwner = useCallback(async (
    cycle: CycleSummary,
    ownerManagerId: number | null,
  ): Promise<void> => {
    if (!user || !isAdmin) {
      return;
    }
    if (!ownerManagerId || ownerManagerId <= 0) {
      setAdminCycleError("Select a valid cycle owner.");
      return;
    }
    const ownerUser = adminUsers.find((row) => row.id === ownerManagerId);
    if (!ownerUser || !ownerUser.is_active || (ownerUser.role !== "manager" && ownerUser.role !== "admin")) {
      setAdminCycleError("Cycle owner must be an active manager or admin.");
      return;
    }
    setAdminCycleError("");
    try {
      await updateCycleMutation({
        actor_username: user.username,
        cycle_id: cycle.id,
        title: cycle.title,
        start_date: String(cycle.start_date || ""),
        end_date: String(cycle.end_date || ""),
        is_active: Boolean(cycle.is_active),
        owner_manager_id: ownerManagerId,
      });
      setAdminCycleMessage("Cycle owner updated.");
      await loadAdminCycles(user);
    } catch (error) {
      setAdminCycleError(String(error instanceof Error ? error.message : error));
    }
  }, [adminUsers, isAdmin, loadAdminCycles, setAdminCycleError, user]);

  return {
    adminCycleMessage,
    setAdminCycleMessage,
    adminUserDraft,
    setAdminUserDraft,
    adminTeamDraft,
    setAdminTeamDraft,
    adminResetDraft,
    setAdminResetDraft,
    adminBackupFile,
    setAdminBackupFile,
    adminBackupConfirm,
    setAdminBackupConfirm,
    adminBackupRestoreResult,
    setAdminBackupRestoreResult,
    adminBackupPending,
    adminCreateCycleDraft,
    setAdminCreateCycleDraft,
    handleAdminBackupExport,
    handleAdminBackupRestore,
    handleAdminCreateUser,
    handleAdminToggleUserActive,
    handleAdminCreateTeam,
    handleAdminUpdateTeam,
    handleAdminDeleteTeam,
    handleAdminResetPassword,
    handleAdminCreateCycle,
    handleAdminSetCycleActive,
    handleAdminUpdateCycleOwner,
    handleAdminDeleteCycle,
  };
}
