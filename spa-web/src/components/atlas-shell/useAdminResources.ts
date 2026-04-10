"use client";

import { useCallback, useState } from "react";

import {
  readAdminAiHealth,
  readAdminPdfHealth,
  readBackendQuery,
  readCyclesQuery,
  type AdminAiHealthResponse,
  type AdminPdfHealthResponse,
  type AuthUser,
  type CycleSummary,
  type TeamMutationResponse,
  type UserMutationResponse,
} from "@/lib/api";

type AdminUserRead = UserMutationResponse;
type AdminTeamRead = TeamMutationResponse;

export default function useAdminResources() {
  const [adminCycles, setAdminCycles] = useState<CycleSummary[]>([]);
  const [adminCyclesPending, setAdminCyclesPending] = useState(false);
  const [adminUsers, setAdminUsers] = useState<AdminUserRead[]>([]);
  const [adminTeams, setAdminTeams] = useState<AdminTeamRead[]>([]);
  const [adminDataPending, setAdminDataPending] = useState(false);
  const [adminCycleError, setAdminCycleError] = useState("");
  const [adminDataError, setAdminDataError] = useState("");
  const [adminAiHealth, setAdminAiHealth] = useState<AdminAiHealthResponse | null>(null);
  const [adminPdfHealth, setAdminPdfHealth] = useState<AdminPdfHealthResponse | null>(null);
  const [adminHealthPending, setAdminHealthPending] = useState(false);

  const loadAdminCycles = useCallback(async (activeUser: AuthUser): Promise<void> => {
    setAdminCyclesPending(true);
    setAdminCycleError("");
    try {
      const cycles = await readCyclesQuery({
        actor_username: activeUser.username,
        kind: "cycles.all",
      });
      const sorted = [...cycles].sort((left, right) => right.id - left.id);
      setAdminCycles(sorted);
    } catch (error) {
      setAdminCycleError(String(error instanceof Error ? error.message : error));
      setAdminCycles([]);
    } finally {
      setAdminCyclesPending(false);
    }
  }, []);

  const loadAdminUsersAndTeams = useCallback(async (activeUser: AuthUser): Promise<void> => {
    setAdminDataPending(true);
    setAdminDataError("");
    try {
      const [usersPayload, teamsPayload] = await Promise.all([
        readBackendQuery({
          actor_username: activeUser.username,
          kind: "users.all",
        }),
        readBackendQuery({
          actor_username: activeUser.username,
          kind: "teams.all",
        }),
      ]);
      const users = ((usersPayload.users as AdminUserRead[]) || []).sort((a, b) =>
        String(a.username || "").localeCompare(String(b.username || "")),
      );
      const teams = ((teamsPayload.teams as AdminTeamRead[]) || []).sort((a, b) =>
        String(a.name || "").localeCompare(String(b.name || "")),
      );
      setAdminUsers(users);
      setAdminTeams(teams);
    } catch (error) {
      setAdminDataError(String(error instanceof Error ? error.message : error));
      setAdminUsers([]);
      setAdminTeams([]);
    } finally {
      setAdminDataPending(false);
    }
  }, []);

  const loadAdminResources = useCallback(async (activeUser: AuthUser): Promise<void> => {
    await Promise.all([loadAdminCycles(activeUser), loadAdminUsersAndTeams(activeUser)]);
  }, [loadAdminCycles, loadAdminUsersAndTeams]);

  const loadAdminHealth = useCallback(async (activeUser: AuthUser, liveProbe: boolean): Promise<void> => {
    setAdminHealthPending(true);
    setAdminDataError("");
    try {
      const [aiHealth, pdfHealth] = await Promise.all([
        readAdminAiHealth({
          actor_username: activeUser.username,
          live_probe: liveProbe,
        }),
        readAdminPdfHealth({
          actor_username: activeUser.username,
        }),
      ]);
      setAdminAiHealth(aiHealth);
      setAdminPdfHealth(pdfHealth);
    } catch (error) {
      setAdminDataError(String(error instanceof Error ? error.message : error));
    } finally {
      setAdminHealthPending(false);
    }
  }, []);

  return {
    adminCycles,
    adminCyclesPending,
    adminUsers,
    adminTeams,
    setAdminTeams,
    adminDataPending,
    adminCycleError,
    setAdminCycleError,
    adminDataError,
    setAdminDataError,
    adminAiHealth,
    adminPdfHealth,
    adminHealthPending,
    loadAdminCycles,
    loadAdminUsersAndTeams,
    loadAdminResources,
    loadAdminHealth,
  };
}
