import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const changeOwnPasswordMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api/auth", () => ({ changeOwnPassword: changeOwnPasswordMock }));

import SidebarAccountCard from "@/components/atlas-shell/SidebarAccountCard";
import type { AuthUser } from "@/lib/api/auth";

function makeUser(role: string): AuthUser {
  return {
    id: 7,
    username: `${role}-user`,
    display_name: `${role} person`,
    role,
    must_change_password: false,
  };
}

describe("SidebarAccountCard", () => {
  beforeEach(() => {
    changeOwnPasswordMock.mockReset();
  });

  it("shows the change-password entry to a member", () => {
    render(<SidebarAccountCard user={makeUser("member")} isAdmin={false} onSignOut={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Change password" })).toBeTruthy();
  });

  it("shows the change-password entry to a manager, who has no admin panel", () => {
    render(<SidebarAccountCard user={makeUser("manager")} isAdmin={false} onSignOut={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Change password" })).toBeTruthy();
  });

  it("hides it from an admin, whose admin panel already offers it", () => {
    render(<SidebarAccountCard user={makeUser("admin")} isAdmin onSignOut={vi.fn()} />);

    expect(screen.queryByRole("button", { name: "Change password" })).toBeNull();
  });

  it("still shows who is signed in and keeps Sign out for an admin", () => {
    const onSignOut = vi.fn();
    render(<SidebarAccountCard user={makeUser("admin")} isAdmin onSignOut={onSignOut} />);

    expect(screen.getByText("Signed in as")).toBeTruthy();
    expect(screen.getByText("admin person")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(onSignOut).toHaveBeenCalledTimes(1);
  });
});