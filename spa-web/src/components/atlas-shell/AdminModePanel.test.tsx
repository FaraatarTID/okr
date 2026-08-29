import React from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import AdminModePanel from "@/components/atlas-shell/AdminModePanel";

function makeProps(overrides: Record<string, unknown> = {}) {
  const cycle = {
    id: 1,
    title: "Q1-2026",
    start_date: "2026-01-01",
    end_date: "2026-03-31",
    is_active: true,
    owner_manager_id: 8,
  };
  const user = {
    id: 8,
    username: "alex",
    display_name: "Alex",
    role: "manager" as const,
    is_active: true,
    must_change_password: false,
  };
  const team = { id: 3, name: "Platform", description: "Core team" };

  return {
    isAdmin: true,
    isManager: false,
    adminTab: "cycles" as const,
    setAdminTab: vi.fn(),
    adminCreateCycleDraft: { title: "", startDate: "", endDate: "", isActive: false, ownerManagerId: "" },
    setAdminCreateCycleDraft: vi.fn(),
    onAdminCreateCycle: vi.fn(),
    adminUserDraft: {
      username: "",
      displayName: "",
      password: "",
      role: "member" as const,
      managerId: "",
      teamId: "",
      mustChangePassword: false,
    },
    setAdminUserDraft: vi.fn(),
    onAdminCreateUser: vi.fn(),
    adminTeamDraft: { name: "", description: "" },
    setAdminTeamDraft: vi.fn(),
    onAdminCreateTeam: vi.fn(),
    adminResetDraft: { userId: "", newPassword: "", requireChange: false },
    setAdminResetDraft: vi.fn(),
    onAdminResetPassword: vi.fn(),
    adminBackupPending: false,
    onAdminBackupExport: vi.fn(),
    setAdminBackupFile: vi.fn(),
    setAdminBackupRestoreResult: vi.fn(),
    adminBackupConfirm: "",
    setAdminBackupConfirm: vi.fn(),
    onAdminBackupRestore: vi.fn(),
    adminBackupRestoreResult: null,
    formatOptionalDate: (value: unknown) => String(value || ""),
    adminHealthPending: false,
    onLoadAdminHealthConfig: vi.fn(),
    onLoadAdminHealthLive: vi.fn(),
    adminAuditSummary: null,
    adminAuditSummaryPending: false,
    adminAuditSummaryError: "",
    onLoadAdminAuditSummary: vi.fn(),
    adminAiHealth: null,
    adminPdfHealth: null,
    adminCyclesPending: false,
    adminDataPending: false,
    adminCycleError: "",
    adminDataError: "",
    adminCycleMessage: "",
    setAdminCycleMessage: vi.fn(),
    adminCycles: [cycle],
    onAdminSetCycleActive: vi.fn(),
    onAdminUpdateCycleOwner: vi.fn(),
    onAdminDeleteCycle: vi.fn(),
    cyclePeriodLabel: () => "Jan to Mar",
    toDateInputValue: (value: unknown) => String(value || ""),
    adminUsers: [user],
    onAdminToggleUserActive: vi.fn(),
    adminTeams: [team],
    setAdminTeams: vi.fn(),
    onAdminUpdateTeam: vi.fn(),
    onAdminDeleteTeam: vi.fn(),
    ...overrides,
  };
}

describe("AdminModePanel", () => {
  it("blocks non-admin users", () => {
    render(<AdminModePanel {...makeProps({ isAdmin: false, isManager: false })} />);

    expect(screen.getByText("Admin or manager role required.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cycles" })).not.toBeInTheDocument();
  });

  it("wires cycle tab actions and lifecycle row controls", async () => {
    const user = userEvent.setup();
    const setAdminCreateCycleDraft = vi.fn();
    const cycleDraftTransitions: Array<{
      title: string;
      startDate: string;
      endDate: string;
      isActive: boolean;
      ownerManagerId: string;
    }> = [];
    setAdminCreateCycleDraft.mockImplementation((update) => {
      if (typeof update === "function") {
        cycleDraftTransitions.push(
          update({ title: "", startDate: "", endDate: "", isActive: false, ownerManagerId: "" }),
        );
      }
    });
    const onAdminCreateCycle = vi.fn();
    const onAdminSetCycleActive = vi.fn();
    const onAdminUpdateCycleOwner = vi.fn();
    const onAdminDeleteCycle = vi.fn();
    const cycle = {
      id: 2,
      title: "Q2-2026",
      start_date: "2026-04-01",
      end_date: "2026-06-30",
      is_active: true,
      owner_manager_id: 8,
    };

    render(
      <AdminModePanel
        {...makeProps({
          adminTab: "cycles",
          setAdminCreateCycleDraft,
          onAdminCreateCycle,
          onAdminSetCycleActive,
          onAdminUpdateCycleOwner,
          onAdminDeleteCycle,
          adminCycles: [cycle],
        })}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText("Cycle title (example: Q1-2026)"), {
      target: { value: "Q3-2026" },
    });
    expect(cycleDraftTransitions[0].title).toBe("Q3-2026");

    await user.click(screen.getByRole("button", { name: "Create cycle" }));
    await user.selectOptions(screen.getByDisplayValue("Alex"), "8");
    await user.click(screen.getByRole("button", { name: "Save owner" }));
    await user.click(screen.getByRole("button", { name: "Deactivate" }));
    await user.click(screen.getByRole("button", { name: "Delete" }));

    expect(onAdminCreateCycle).toHaveBeenCalledTimes(1);
    expect(onAdminUpdateCycleOwner).toHaveBeenCalledWith(cycle, 8);
    expect(onAdminSetCycleActive).toHaveBeenCalledWith(cycle, false);
    expect(onAdminDeleteCycle).toHaveBeenCalledWith(cycle);
  });

  it("wires users and teams tab actions", async () => {
    const user = userEvent.setup();
    const setAdminUserDraft = vi.fn();
    const userDraftTransitions: Array<{
      username: string;
      displayName: string;
      password: string;
      role: "admin" | "manager" | "member";
      managerId: string;
      teamId: string;
      mustChangePassword: boolean;
    }> = [];
    setAdminUserDraft.mockImplementation((update) => {
      if (typeof update === "function") {
        userDraftTransitions.push(
          update({
            username: "",
            displayName: "",
            password: "",
            role: "member",
            managerId: "",
            teamId: "",
            mustChangePassword: false,
          }),
        );
      }
    });
    const onAdminCreateUser = vi.fn();
    const onAdminToggleUserActive = vi.fn();
    const setAdminTeams = vi.fn();
    const teamTransitions: Array<Array<{ id: number; name: string; description?: string | null }>> = [];
    setAdminTeams.mockImplementation((update) => {
      if (typeof update === "function") {
        teamTransitions.push(update([{ id: 9, name: "Delivery", description: "Delivery org" }]));
      }
    });
    const onAdminCreateTeam = vi.fn();
    const onAdminUpdateTeam = vi.fn();
    const onAdminDeleteTeam = vi.fn();
    const setAdminTab = vi.fn();
    const team = { id: 9, name: "Delivery", description: "Delivery org" };

    const { rerender } = render(
      <AdminModePanel
        {...makeProps({
          adminTab: "users",
          setAdminTab,
          setAdminUserDraft,
          onAdminCreateUser,
          onAdminToggleUserActive,
          adminUsers: [
            {
              id: 21,
              username: "sam",
              display_name: "Sam",
              role: "member",
              is_active: true,
              must_change_password: false,
            },
          ],
        })}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Teams" }));
    expect(setAdminTab).toHaveBeenCalledWith("teams");

    fireEvent.change(screen.getByPlaceholderText("Username"), { target: { value: "newuser" } });
    expect(userDraftTransitions[0].username).toBe("newuser");

    await user.click(screen.getByRole("button", { name: "Create user" }));
    await user.click(screen.getByRole("button", { name: "Deactivate" }));
    expect(onAdminCreateUser).toHaveBeenCalledTimes(1);
    expect(onAdminToggleUserActive).toHaveBeenCalledWith(
      expect.objectContaining({ id: 21, username: "sam" }),
    );

    rerender(
      <AdminModePanel
        {...makeProps({
          adminTab: "teams",
          setAdminTeams,
          onAdminCreateTeam,
          onAdminUpdateTeam,
          onAdminDeleteTeam,
          adminTeams: [team],
        })}
      />,
    );

    fireEvent.change(screen.getByDisplayValue("Delivery"), { target: { value: "Ops" } });
    expect(teamTransitions[0][0].name).toBe("Ops");

    await user.click(screen.getByRole("button", { name: "Create team" }));
    await user.click(screen.getByRole("button", { name: "Update" }));
    await user.click(screen.getByRole("button", { name: "Delete" }));

    expect(onAdminCreateTeam).toHaveBeenCalledTimes(1);
    expect(onAdminUpdateTeam).toHaveBeenCalledWith(team);
    expect(onAdminDeleteTeam).toHaveBeenCalledWith(team);
  });

  it("shows audit summary content and refresh action", async () => {
    const user = userEvent.setup();
    const onLoadAdminAuditSummary = vi.fn();

    render(
      <AdminModePanel
        {...makeProps({
          adminTab: "audit",
          onLoadAdminAuditSummary,
          adminAuditSummary: {
            total_events: 3,
            success_events: 2,
            failure_events: 1,
            latest_event_at: "2026-07-22T00:00:00Z",
            by_actor_role: [{ value: "admin", count: 3 }],
            by_actor_team_id: [{ value: 8, count: 3 }],
            by_target_type: [{ value: "goal", count: 2 }],
            by_entity: [{ value: "goal", count: 2 }],
            by_action: [{ value: "create", count: 2 }],
            recent_events: [
              {
                id: 1,
                actor: "alice",
                action: "create",
                entity: "goal",
                result: "success",
                target_type: "goal",
                created_at: "2026-07-22T00:00:00Z",
              },
            ],
          },
        })}
      />,
    );

    expect(screen.getByText("Audit summary")).toBeInTheDocument();
    expect(screen.getByText("Events")).toBeInTheDocument();
    expect(screen.getByText("create / goal")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Refresh Summary" }));
    expect(onLoadAdminAuditSummary).toHaveBeenCalledTimes(1);
  });
});
