"use client";

import { useCallback, useState } from "react";

import {
  readAdminAiHealth,
  readAuditSummary,
  readAdminPdfHealth,
  readBackendQuery,
  readCyclesQuery,
  type AdminAiHealthResponse,
  type AdminPdfHealthResponse,
  type AuditSummaryResponse,
  type AuthUser,
  type CycleSummary,
  type ReadQueryTeam,
  type ReadQueryUser,
} from "@/lib/api";

type AdminUserRead = ReadQueryUser;
type AdminTeamRead = ReadQueryTeam;

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
  const [adminAuditSummary, setAdminAuditSummary] = useState<AuditSummaryResponse | null>(null);
  const [adminAuditSummaryPending, setAdminAuditSummaryPending] = useState(false);
  const [adminAuditSummaryError, setAdminAuditSummaryError] = useState("");

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
      const users = (usersPayload.users || []).sort((a, b) =>
        String(a.username || "").localeCompare(String(b.username || "")),
      );
      const teams = (teamsPayload.teams || []).sort((a, b) =>
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

  const loadAdminAuditSummary = useCallback(async (activeUser: AuthUser): Promise<void> => {
    setAdminAuditSummaryPending(true);
    setAdminAuditSummaryError("");
    try {
      const summary = await readAuditSummary({
        actor_username: activeUser.username,
        days: 30,
        recent_limit: 10,
      });
      setAdminAuditSummary(summary);
    } catch (error) {
      setAdminAuditSummaryError(String(error instanceof Error ? error.message : error));
      setAdminAuditSummary(null);
    } finally {
      setAdminAuditSummaryPending(false);
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
    adminAuditSummary,
    adminAuditSummaryPending,
    adminAuditSummaryError,
    loadAdminCycles,
    loadAdminUsersAndTeams,
    loadAdminResources,
    loadAdminHealth,
    loadAdminAuditSummary,
  };
}
