"use client";

import { useMemo, useState, type Dispatch, type SetStateAction } from "react";

import type {
  AdminAiHealthResponse,
  AdminDbRestoreResponse,
  AdminPdfHealthResponse,
  CycleSummary,
  TeamMutationResponse,
  UserMutationResponse,
} from "@/lib/api";

export type AdminTab = "cycles" | "users" | "teams" | "security" | "backup" | "ai";

export type AdminUserDraft = {
  username: string;
  displayName: string;
  password: string;
  role: "admin" | "manager" | "member";
  managerId: string;
  teamId: string;
  mustChangePassword: boolean;
};

export type AdminTeamDraft = {
  name: string;
  description: string;
};

export type AdminResetDraft = {
  userId: string;
  newPassword: string;
  requireChange: boolean;
};

export type AdminCreateCycleDraft = {
  title: string;
  startDate: string;
  endDate: string;
  isActive: boolean;
  ownerManagerId: string;
};

type AdminModePanelProps = {
  isAdmin: boolean;
  adminTab: AdminTab;
  setAdminTab: (value: AdminTab) => void;
  adminCreateCycleDraft: AdminCreateCycleDraft;
  setAdminCreateCycleDraft: Dispatch<SetStateAction<AdminCreateCycleDraft>>;
  onAdminCreateCycle: () => void;
  adminUserDraft: AdminUserDraft;
  setAdminUserDraft: Dispatch<SetStateAction<AdminUserDraft>>;
  onAdminCreateUser: () => void;
  adminTeamDraft: AdminTeamDraft;
  setAdminTeamDraft: Dispatch<SetStateAction<AdminTeamDraft>>;
  onAdminCreateTeam: () => void;
  adminResetDraft: AdminResetDraft;
  setAdminResetDraft: Dispatch<SetStateAction<AdminResetDraft>>;
  onAdminResetPassword: () => void;
  adminBackupPending: boolean;
  onAdminBackupExport: () => void;
  setAdminBackupFile: Dispatch<SetStateAction<File | null>>;
  setAdminBackupRestoreResult: Dispatch<SetStateAction<AdminDbRestoreResponse | null>>;
  adminBackupConfirm: string;
  setAdminBackupConfirm: Dispatch<SetStateAction<string>>;
  onAdminBackupRestore: () => void;
  adminBackupRestoreResult: AdminDbRestoreResponse | null;
  formatOptionalDate: (value: unknown) => string;
  adminHealthPending: boolean;
  onLoadAdminHealthConfig: () => void;
  onLoadAdminHealthLive: () => void;
  adminAiHealth: AdminAiHealthResponse | null;
  adminPdfHealth: AdminPdfHealthResponse | null;
  adminCyclesPending: boolean;
  adminDataPending: boolean;
  adminCycleError: string;
  adminDataError: string;
  adminCycleMessage: string;
  adminCycles: CycleSummary[];
  onAdminSetCycleActive: (cycle: CycleSummary, isActive: boolean) => void;
  onAdminUpdateCycleOwner: (cycle: CycleSummary, ownerManagerId: number | null) => void;
  onAdminDeleteCycle: (cycle: CycleSummary) => void;
  cyclePeriodLabel: (cycle: Pick<CycleSummary, "start_date" | "end_date"> | null) => string;
  toDateInputValue: (value: unknown) => string;
  adminUsers: UserMutationResponse[];
  onAdminToggleUserActive: (user: UserMutationResponse) => void;
  adminTeams: TeamMutationResponse[];
  setAdminTeams: Dispatch<SetStateAction<TeamMutationResponse[]>>;
  onAdminUpdateTeam: (team: TeamMutationResponse) => void;
  onAdminDeleteTeam: (team: TeamMutationResponse) => void;
};

export default function AdminModePanel({
  isAdmin,
  adminTab,
  setAdminTab,
  adminCreateCycleDraft,
  setAdminCreateCycleDraft,
  onAdminCreateCycle,
  adminUserDraft,
  setAdminUserDraft,
  onAdminCreateUser,
  adminTeamDraft,
  setAdminTeamDraft,
  onAdminCreateTeam,
  adminResetDraft,
  setAdminResetDraft,
  onAdminResetPassword,
  adminBackupPending,
  onAdminBackupExport,
  setAdminBackupFile,
  setAdminBackupRestoreResult,
  adminBackupConfirm,
  setAdminBackupConfirm,
  onAdminBackupRestore,
  adminBackupRestoreResult,
  formatOptionalDate,
  adminHealthPending,
  onLoadAdminHealthConfig,
  onLoadAdminHealthLive,
  adminAiHealth,
  adminPdfHealth,
  adminCyclesPending,
  adminDataPending,
  adminCycleError,
  adminDataError,
  adminCycleMessage,
  adminCycles,
  onAdminSetCycleActive,
  onAdminUpdateCycleOwner,
  onAdminDeleteCycle,
  cyclePeriodLabel,
  toDateInputValue,
  adminUsers,
  onAdminToggleUserActive,
  adminTeams,
  setAdminTeams,
  onAdminUpdateTeam,
  onAdminDeleteTeam,
}: AdminModePanelProps) {
  const [cycleOwnerDraftById, setCycleOwnerDraftById] = useState<Record<number, string>>({});
  const managerOptions = useMemo(
    () =>
      adminUsers
        .filter((row) => row.is_active && (row.role === "manager" || row.role === "admin"))
        .sort((a, b) =>
          String(a.display_name || a.username || "")
            .toLowerCase()
            .localeCompare(String(b.display_name || b.username || "").toLowerCase()),
        ),
    [adminUsers],
  );
  const userLabelById = useMemo(() => {
    const map = new Map<number, string>();
    for (const row of adminUsers) {
      map.set(row.id, String(row.display_name || row.username || "").trim() || row.username);
    }
    return map;
  }, [adminUsers]);
  const teamLabelById = useMemo(() => {
    const map = new Map<number, string>();
    for (const row of adminTeams) {
      map.set(row.id, String(row.name || "").trim() || `Team ${row.id}`);
    }
    return map;
  }, [adminTeams]);
  return (
    <section className="panel" style={{ marginTop: "0.9rem", padding: "0.9rem" }}>
      <p className="kicker">Admin</p>
      <h2 style={{ margin: "0.1rem 0 0.45rem", fontSize: "1.05rem" }}>Platform Controls</h2>
      {!isAdmin ? (
        <p style={{ margin: 0, color: "var(--error)" }}>Admin role required.</p>
      ) : (
        <>
          <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap", marginBottom: "0.6rem" }}>
            <button className="primary-button" type="button" onClick={() => setAdminTab("cycles")}>
              Cycles
            </button>
            <button className="primary-button" type="button" onClick={() => setAdminTab("users")}>
              Users
            </button>
            <button className="primary-button" type="button" onClick={() => setAdminTab("teams")}>
              Teams
            </button>
            <button className="primary-button" type="button" onClick={() => setAdminTab("security")}>
              Security
            </button>
            <button className="primary-button" type="button" onClick={() => setAdminTab("backup")}>
              Backup
            </button>
            <button className="primary-button" type="button" onClick={() => setAdminTab("ai")}>
              AI/PDF Health
            </button>
          </div>
          <div
            style={{
              border: "1px solid var(--line)",
              borderRadius: 10,
              background: "var(--surface)",
              padding: "0.6rem",
              marginBottom: "0.8rem",
            }}
          >
            {adminTab === "cycles" ? (
              <>
                <p className="kicker" style={{ margin: 0 }}>
                  Create cycle
                </p>
                <div className="grid-2" style={{ marginTop: "0.45rem", gap: "0.5rem" }}>
                  <input
                    className="input"
                    value={adminCreateCycleDraft.title}
                    onChange={(event) =>
                      setAdminCreateCycleDraft((prev) => ({ ...prev, title: event.target.value }))
                    }
                    placeholder="Cycle title (example: Q1-2026)"
                  />
                  <label style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontSize: "0.86rem" }}>
                    <input
                      type="checkbox"
                      checked={adminCreateCycleDraft.isActive}
                      onChange={(event) =>
                        setAdminCreateCycleDraft((prev) => ({ ...prev, isActive: event.target.checked }))
                      }
                    />
                    Active cycle
                  </label>
                  <input
                    type="date"
                    className="input"
                    value={adminCreateCycleDraft.startDate}
                    onChange={(event) =>
                      setAdminCreateCycleDraft((prev) => ({ ...prev, startDate: event.target.value }))
                    }
                  />
                  <input
                    type="date"
                    className="input"
                    value={adminCreateCycleDraft.endDate}
                    onChange={(event) =>
                      setAdminCreateCycleDraft((prev) => ({ ...prev, endDate: event.target.value }))
                    }
                  />
                  <select
                    className="input"
                    value={adminCreateCycleDraft.ownerManagerId}
                    onChange={(event) =>
                      setAdminCreateCycleDraft((prev) => ({ ...prev, ownerManagerId: event.target.value }))
                    }
                  >
                    <option value="">Select cycle owner (manager/admin)</option>
                    {managerOptions.map((row) => (
                      <option key={`cycle-owner-${row.id}`} value={String(row.id)}>
                        {String(row.display_name || row.username || "").trim() || row.username}
                      </option>
                    ))}
                  </select>
                </div>
                <button
                  className="primary-button"
                  type="button"
                  onClick={onAdminCreateCycle}
                  style={{ marginTop: "0.5rem" }}
                >
                  Create cycle
                </button>
              </>
            ) : null}

            {adminTab === "users" ? (
              <>
                <p className="kicker" style={{ margin: 0 }}>
                  Create user
                </p>
                <div className="grid-2" style={{ marginTop: "0.45rem", gap: "0.5rem" }}>
                  <input
                    className="input"
                    value={adminUserDraft.username}
                    onChange={(event) => setAdminUserDraft((prev) => ({ ...prev, username: event.target.value }))}
                    placeholder="Username"
                  />
                  <input
                    className="input"
                    value={adminUserDraft.displayName}
                    onChange={(event) => setAdminUserDraft((prev) => ({ ...prev, displayName: event.target.value }))}
                    placeholder="Display name"
                  />
                  <input
                    className="input"
                    type="password"
                    value={adminUserDraft.password}
                    onChange={(event) => setAdminUserDraft((prev) => ({ ...prev, password: event.target.value }))}
                    placeholder="Password"
                  />
                  <select
                    className="input"
                    value={adminUserDraft.role}
                    onChange={(event) =>
                      setAdminUserDraft((prev) => ({
                        ...prev,
                        role: event.target.value as "admin" | "manager" | "member",
                      }))
                    }
                  >
                    <option value="member">member</option>
                    <option value="manager">manager</option>
                    <option value="admin">admin</option>
                  </select>
                  <select
                    className="input"
                    value={adminUserDraft.managerId}
                    onChange={(event) => setAdminUserDraft((prev) => ({ ...prev, managerId: event.target.value }))}
                    disabled={adminUserDraft.role !== "member"}
                  >
                    <option value="">
                      {adminUserDraft.role === "member" ? "Select manager" : "Manager not required"}
                    </option>
                    {managerOptions.map((row) => (
                      <option key={`user-manager-${row.id}`} value={String(row.id)}>
                        {String(row.display_name || row.username || "").trim() || row.username}
                      </option>
                    ))}
                  </select>
                  <select
                    className="input"
                    value={adminUserDraft.teamId}
                    onChange={(event) => setAdminUserDraft((prev) => ({ ...prev, teamId: event.target.value }))}
                  >
                    <option value="">Select team (optional)</option>
                    {adminTeams
                      .slice()
                      .sort((a, b) => String(a.name || "").localeCompare(String(b.name || "")))
                      .map((row) => (
                        <option key={`user-team-${row.id}`} value={String(row.id)}>
                          {String(row.name || "").trim() || `Team ${row.id}`}
                        </option>
                      ))}
                  </select>
                </div>
                <label style={{ marginTop: "0.4rem", display: "flex", alignItems: "center", gap: "0.4rem", fontSize: "0.86rem" }}>
                  <input
                    type="checkbox"
                    checked={adminUserDraft.mustChangePassword}
                    onChange={(event) =>
                      setAdminUserDraft((prev) => ({ ...prev, mustChangePassword: event.target.checked }))
                    }
                  />
                  Require password change at first login
                </label>
                <button className="primary-button" type="button" onClick={onAdminCreateUser} style={{ marginTop: "0.5rem" }}>
                  Create user
                </button>
              </>
            ) : null}

            {adminTab === "teams" ? (
              <>
                <p className="kicker" style={{ margin: 0 }}>
                  Create team
                </p>
                <div className="grid-2" style={{ marginTop: "0.45rem", gap: "0.5rem" }}>
                  <input
                    className="input"
                    value={adminTeamDraft.name}
                    onChange={(event) => setAdminTeamDraft((prev) => ({ ...prev, name: event.target.value }))}
                    placeholder="Team name"
                  />
                  <input
                    className="input"
                    value={adminTeamDraft.description}
                    onChange={(event) => setAdminTeamDraft((prev) => ({ ...prev, description: event.target.value }))}
                    placeholder="Description (optional)"
                  />
                </div>
                <button className="primary-button" type="button" onClick={onAdminCreateTeam} style={{ marginTop: "0.5rem" }}>
                  Create team
                </button>
              </>
            ) : null}

            {adminTab === "security" ? (
              <>
                <p className="kicker" style={{ margin: 0 }}>
                  Reset user password
                </p>
                <div className="grid-2" style={{ marginTop: "0.45rem", gap: "0.5rem" }}>
                  <select
                    className="input"
                    value={adminResetDraft.userId}
                    onChange={(event) => setAdminResetDraft((prev) => ({ ...prev, userId: event.target.value }))}
                  >
                    <option value="">Select user</option>
                    {adminUsers
                      .slice()
                      .sort((a, b) =>
                        String(a.display_name || a.username || "")
                          .toLowerCase()
                          .localeCompare(String(b.display_name || b.username || "").toLowerCase()),
                      )
                      .map((row) => (
                        <option key={`security-user-${row.id}`} value={String(row.id)}>
                          {String(row.display_name || row.username || "").trim() || row.username}
                        </option>
                      ))}
                  </select>
                  <input
                    className="input"
                    type="password"
                    value={adminResetDraft.newPassword}
                    onChange={(event) => setAdminResetDraft((prev) => ({ ...prev, newPassword: event.target.value }))}
                    placeholder="New password"
                  />
                </div>
                <label style={{ marginTop: "0.4rem", display: "flex", alignItems: "center", gap: "0.4rem", fontSize: "0.86rem" }}>
                  <input
                    type="checkbox"
                    checked={adminResetDraft.requireChange}
                    onChange={(event) => setAdminResetDraft((prev) => ({ ...prev, requireChange: event.target.checked }))}
                  />
                  Require change at next login
                </label>
                <button className="primary-button" type="button" onClick={onAdminResetPassword} style={{ marginTop: "0.5rem" }}>
                  Reset password
                </button>
              </>
            ) : null}

            {adminTab === "backup" ? (
              <>
                <p className="kicker" style={{ margin: 0 }}>
                  Database backup/restore
                </p>
                <p style={{ margin: "0.35rem 0 0", color: "var(--ink-soft)" }}>
                  Restore is guarded and requires `OKR_ENABLE_DIRECT_DB_RESTORE=true` plus non-production runtime.
                </p>
                <button
                  className="primary-button"
                  type="button"
                  onClick={onAdminBackupExport}
                  disabled={adminBackupPending}
                  style={{ marginTop: "0.5rem" }}
                >
                  {adminBackupPending ? "Working..." : "Download Backup JSON"}
                </button>
                <div style={{ marginTop: "0.6rem" }}>
                  <input
                    type="file"
                    accept=".json,application/json"
                    onChange={(event) => {
                      const file = event.target.files?.[0] || null;
                      setAdminBackupFile(file);
                      setAdminBackupRestoreResult(null);
                    }}
                  />
                </div>
                <input
                  className="input"
                  value={adminBackupConfirm}
                  onChange={(event) => setAdminBackupConfirm(event.target.value)}
                  placeholder='Type RESTORE to confirm'
                  style={{ marginTop: "0.45rem" }}
                />
                <button
                  className="primary-button"
                  type="button"
                  onClick={onAdminBackupRestore}
                  disabled={adminBackupPending}
                  style={{ marginTop: "0.5rem" }}
                >
                  {adminBackupPending ? "Working..." : "Restore Backup"}
                </button>
                {adminBackupRestoreResult ? (
                  <div style={{ marginTop: "0.55rem", border: "1px solid var(--line)", borderRadius: 10, padding: "0.55rem" }}>
                    <div style={{ fontSize: "0.84rem", color: "var(--ink-soft)" }}>Restore summary</div>
                    <p style={{ margin: "0.2rem 0 0" }}>Format: {String(adminBackupRestoreResult.format || "-")}</p>
                    <p style={{ margin: "0.2rem 0 0" }}>
                      Exported at: {formatOptionalDate(adminBackupRestoreResult.exported_at)}
                    </p>
                    <details style={{ marginTop: "0.3rem" }}>
                      <summary style={{ cursor: "pointer", fontSize: "0.84rem", color: "var(--ink-soft)" }}>
                        Restored row counts
                      </summary>
                      <pre style={{ margin: "0.3rem 0 0", whiteSpace: "pre-wrap", fontSize: "0.8rem" }}>
                        {JSON.stringify(adminBackupRestoreResult.restored_counts || {}, null, 2)}
                      </pre>
                    </details>
                  </div>
                ) : null}
              </>
            ) : null}

            {adminTab === "ai" ? (
              <>
                <p className="kicker" style={{ margin: 0 }}>
                  AI/PDF health
                </p>
                <div style={{ display: "flex", gap: "0.45rem", marginTop: "0.45rem", flexWrap: "wrap" }}>
                  <button
                    className="primary-button"
                    type="button"
                    disabled={adminHealthPending}
                    onClick={onLoadAdminHealthConfig}
                  >
                    {adminHealthPending ? "Checking..." : "Check Config Only"}
                  </button>
                  <button
                    className="primary-button"
                    type="button"
                    disabled={adminHealthPending}
                    onClick={onLoadAdminHealthLive}
                  >
                    {adminHealthPending ? "Checking..." : "Run Live Probe"}
                  </button>
                </div>
                {adminAiHealth ? (
                  <div style={{ marginTop: "0.55rem", border: "1px solid var(--line)", borderRadius: 10, padding: "0.55rem" }}>
                    <div style={{ fontSize: "0.84rem", color: "var(--ink-soft)" }}>AI Provider</div>
                    <p style={{ margin: "0.2rem 0 0" }}>
                      {String(adminAiHealth.provider || "unknown")} - status: {String(adminAiHealth.status || "unknown")}
                    </p>
                    <p style={{ margin: "0.2rem 0 0", color: "var(--ink-soft)" }}>
                      {String(adminAiHealth.probe_message || adminAiHealth.config_message || "")}
                    </p>
                  </div>
                ) : null}
                {adminPdfHealth ? (
                  <div style={{ marginTop: "0.55rem", border: "1px solid var(--line)", borderRadius: 10, padding: "0.55rem" }}>
                    <div style={{ fontSize: "0.84rem", color: "var(--ink-soft)" }}>PDF Runtime</div>
                    <p style={{ margin: "0.2rem 0 0" }}>
                      method: {String(adminPdfHealth.method || "unknown")} - supported: {adminPdfHealth.supported_method ? "yes" : "no"}
                    </p>
                    <p style={{ margin: "0.2rem 0 0", color: "var(--ink-soft)" }}>
                      playwright: {adminPdfHealth.playwright_available ? "available" : "missing"} - pdfshift key:{" "}
                      {adminPdfHealth.pdfshift_api_key_configured ? "set" : "missing"}
                    </p>
                  </div>
                ) : null}
              </>
            ) : null}
          </div>

          {adminCyclesPending || adminDataPending ? (
            <p style={{ margin: "0.3rem 0", color: "var(--ink-soft)" }}>Loading admin data...</p>
          ) : null}
          {adminCycleError ? <p style={{ margin: "0.3rem 0", color: "var(--error)" }}>{adminCycleError}</p> : null}
          {adminDataError ? <p style={{ margin: "0.3rem 0", color: "var(--error)" }}>{adminDataError}</p> : null}
          {adminCycleMessage ? <p style={{ margin: "0.3rem 0", color: "var(--accent)" }}>{adminCycleMessage}</p> : null}

          {adminTab === "cycles" ? (
            <div className="atlas-node-list" style={{ maxHeight: "52vh" }}>
              {adminCycles.length ? (
                adminCycles.map((cycle) => (
                  <div
                    key={cycle.id}
                    style={{
                      border: "1px solid var(--line)",
                      borderRadius: 10,
                      background: "var(--surface-alt)",
                      padding: "0.58rem 0.62rem",
                      marginBottom: "0.45rem",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem", flexWrap: "wrap" }}>
                      <div>
                        <strong>{cycle.title}</strong>
                        <div style={{ fontSize: "0.82rem", color: "var(--ink-soft)", marginTop: "0.1rem" }}>
                          {cyclePeriodLabel(cycle) || `${toDateInputValue(cycle.start_date)} to ${toDateInputValue(cycle.end_date)}`}
                        </div>
                        <div style={{ fontSize: "0.8rem", color: "var(--ink-soft)", marginTop: "0.1rem" }}>
                          Owner: {cycle.owner_manager_id ? (userLabelById.get(cycle.owner_manager_id) || "Unknown manager") : "Unassigned"}
                        </div>
                      </div>
                      <div style={{ fontSize: "0.82rem", color: cycle.is_active ? "var(--accent)" : "var(--ink-soft)" }}>
                        {cycle.is_active ? "Active" : "Inactive"}
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: "0.45rem", marginTop: "0.48rem", flexWrap: "wrap" }}>
                      <select
                        className="input"
                        value={cycleOwnerDraftById[cycle.id] ?? String(cycle.owner_manager_id || "")}
                        onChange={(event) =>
                          setCycleOwnerDraftById((prev) => ({ ...prev, [cycle.id]: event.target.value }))
                        }
                        style={{ minWidth: 220 }}
                      >
                        <option value="">Select owner</option>
                        {managerOptions.map((row) => (
                          <option key={`cycle-owner-row-${cycle.id}-${row.id}`} value={String(row.id)}>
                            {String(row.display_name || row.username || "").trim() || row.username}
                          </option>
                        ))}
                      </select>
                      <button
                        className="primary-button"
                        type="button"
                        onClick={() => {
                          const raw = cycleOwnerDraftById[cycle.id] ?? String(cycle.owner_manager_id || "");
                          const parsed = Number.parseInt(raw, 10);
                          onAdminUpdateCycleOwner(cycle, Number.isFinite(parsed) && parsed > 0 ? parsed : null);
                        }}
                      >
                        Save owner
                      </button>
                      <button
                        className="primary-button"
                        type="button"
                        onClick={() => onAdminSetCycleActive(cycle, !cycle.is_active)}
                      >
                        {cycle.is_active ? "Deactivate" : "Activate"}
                      </button>
                      <button className="primary-button" type="button" onClick={() => onAdminDeleteCycle(cycle)}>
                        Delete
                      </button>
                    </div>
                  </div>
                ))
              ) : (
                <p style={{ margin: 0, color: "var(--ink-soft)" }}>No cycles found.</p>
              )}
            </div>
          ) : null}

          {adminTab === "users" ? (
            <div className="atlas-node-list" style={{ maxHeight: "52vh" }}>
              {adminUsers.length ? (
                adminUsers.map((row) => (
                  <div key={row.id} style={{ border: "1px solid var(--line)", borderRadius: 10, background: "var(--surface-alt)", padding: "0.58rem 0.62rem", marginBottom: "0.45rem" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem", flexWrap: "wrap" }}>
                      <div>
                        <strong>{row.display_name || row.username}</strong>
                        <div style={{ fontSize: "0.82rem", color: "var(--ink-soft)" }}>
                          @{row.username} - {row.role}
                        </div>
                        <div style={{ fontSize: "0.8rem", color: "var(--ink-soft)", marginTop: "0.1rem" }}>
                          Manager: {row.manager_id ? (userLabelById.get(row.manager_id) || "Unknown") : "None"} | Team:{" "}
                          {row.team_id ? (teamLabelById.get(row.team_id) || "Unknown") : "None"}
                        </div>
                      </div>
                      <div style={{ fontSize: "0.82rem", color: row.is_active ? "var(--accent)" : "var(--ink-soft)" }}>
                        {row.is_active ? "Active" : "Inactive"}
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: "0.45rem", marginTop: "0.48rem", flexWrap: "wrap" }}>
                      <button className="primary-button" type="button" onClick={() => onAdminToggleUserActive(row)}>
                        {row.is_active ? "Deactivate" : "Activate"}
                      </button>
                    </div>
                  </div>
                ))
              ) : (
                <p style={{ margin: 0, color: "var(--ink-soft)" }}>No users found.</p>
              )}
            </div>
          ) : null}

          {adminTab === "teams" ? (
            <div className="atlas-node-list" style={{ maxHeight: "52vh" }}>
              {adminTeams.length ? (
                adminTeams.map((team) => (
                  <div key={team.id} style={{ border: "1px solid var(--line)", borderRadius: 10, background: "var(--surface-alt)", padding: "0.58rem 0.62rem", marginBottom: "0.45rem" }}>
                    <input
                      className="input"
                      value={team.name}
                      onChange={(event) =>
                        setAdminTeams((prev) =>
                          prev.map((item) => (item.id === team.id ? { ...item, name: event.target.value } : item)),
                        )
                      }
                    />
                    <input
                      className="input"
                      value={String(team.description || "")}
                      onChange={(event) =>
                        setAdminTeams((prev) =>
                          prev.map((item) =>
                            item.id === team.id ? { ...item, description: event.target.value } : item,
                          ),
                        )
                      }
                      style={{ marginTop: "0.35rem" }}
                    />
                    <div style={{ display: "flex", gap: "0.45rem", marginTop: "0.48rem", flexWrap: "wrap" }}>
                      <button className="primary-button" type="button" onClick={() => onAdminUpdateTeam(team)}>
                        Update
                      </button>
                      <button className="primary-button" type="button" onClick={() => onAdminDeleteTeam(team)}>
                        Delete
                      </button>
                    </div>
                  </div>
                ))
              ) : (
                <p style={{ margin: 0, color: "var(--ink-soft)" }}>No teams found.</p>
              )}
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}

