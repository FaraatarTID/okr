"use client";

import { useCallback, useState } from "react";

import {
  readAdminAiHealth,
  readAuditSummary,
  readAdminPdfHealth,
  type AdminAiHealthResponse,
  type AdminPdfHealthResponse,
  type AuditSummaryView,
  type AuthUser,
  type CycleSummary,
  type ReadQueryTeam,
  type ReadQueryUser,
} from "@/lib/api";
import { readMergedCycles } from "@/lib/cycles";
import { readSortedAdminResources } from "@/lib/adminResources";

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
  const [adminAuditSummary, setAdminAuditSummary] = useState<AuditSummaryView | null>(null);
  const [adminAuditSummaryPending, setAdminAuditSummaryPending] = useState(false);
  const [adminAuditSummaryError, setAdminAuditSummaryError] = useState("");

  const loadAdminCycles = useCallback(
    async (activeUser: AuthUser, options: { bypassCache?: boolean } = {}): Promise<void> => {
      setAdminCyclesPending(true);
      setAdminCycleError("");
      try {
        // Shares the cycle cache with `useCyclesSource` and the deep-link
        // bootstrap, so entering the admin panel does not issue a third
        // `cycles.all` request. The result is already merged and sorted by
        // descending id, which is the order this panel renders.
        const cycles = await readMergedCycles(activeUser.username, {
          bypassCache: options.bypassCache,
        });
        setAdminCycles(cycles);
      } catch (error) {
        setAdminCycleError(String(error instanceof Error ? error.message : error));
        setAdminCycles([]);
      } finally {
        setAdminCyclesPending(false);
      }
    },
    [],
  );

  const loadAdminUsersAndTeams = useCallback(
    async (activeUser: AuthUser, options: { bypassCache?: boolean } = {}): Promise<void> => {
      setAdminDataPending(true);
      setAdminDataError("");
      try {
        // Shares the admin cache, so re-entering the admin panel inside the TTL
        // does not re-request users and teams. Mutation paths pass
        // `bypassCache: true`; the fresh result re-seeds the cache.
        const { users, teams } = await readSortedAdminResources(activeUser.username, {
          bypassCache: options.bypassCache,
        });
        setAdminUsers(users);
        setAdminTeams(teams);
      } catch (error) {
        setAdminDataError(String(error instanceof Error ? error.message : error));
        setAdminUsers([]);
        setAdminTeams([]);
      } finally {
        setAdminDataPending(false);
      }
    },
    [],
  );

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
