import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const changeOwnPasswordMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api/auth", () => ({ changeOwnPassword: changeOwnPasswordMock }));

import PasswordChangePanel from "@/components/PasswordChangePanel";
import type { AuthUser } from "@/lib/api/auth";

const user: AuthUser = {
  id: 42,
  username: "member",
  display_name: "Member",
  role: "member",
  must_change_password: false,
};

describe("PasswordChangePanel", () => {
  beforeEach(() => {
    changeOwnPasswordMock.mockReset();
    changeOwnPasswordMock.mockResolvedValue({ updated: true });
  });

  it("exposes the signed-in password change entry and asks for the current password", () => {
    render(<PasswordChangePanel user={user} compact />);

    fireEvent.click(screen.getByRole("button", { name: "Change password" }));

    expect(screen.getByLabelText("Current password")).toBeTruthy();
    expect(screen.getByLabelText("New password")).toBeTruthy();
    expect(screen.getByLabelText("Confirm new password")).toBeTruthy();
  });

  it("changes the signed-in user's password and keeps the session active", async () => {
    const onComplete = vi.fn();
    render(<PasswordChangePanel user={user} onComplete={onComplete} compact />);
    fireEvent.click(screen.getByRole("button", { name: "Change password" }));
    fireEvent.change(screen.getByLabelText("Current password"), { target: { value: "old-pass" } });
    fireEvent.change(screen.getByLabelText("New password"), { target: { value: "new-password" } });
    fireEvent.change(screen.getByLabelText("Confirm new password"), { target: { value: "new-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Change password" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Password updated successfully.");
    expect(changeOwnPasswordMock).toHaveBeenCalledWith({
      username: "member",
      current_password: "old-pass",
      new_password: "new-password",
    });
    expect(onComplete).toHaveBeenCalledOnce();
    expect(screen.getByLabelText("Current password")).toHaveValue("");
  });

  it("does not submit mismatched new passwords", () => {
    render(<PasswordChangePanel user={user} compact />);
    fireEvent.click(screen.getByRole("button", { name: "Change password" }));
    fireEvent.change(screen.getByLabelText("Current password"), { target: { value: "old-pass" } });
    fireEvent.change(screen.getByLabelText("New password"), { target: { value: "new-password" } });
    fireEvent.change(screen.getByLabelText("Confirm new password"), { target: { value: "different" } });
    fireEvent.click(screen.getByRole("button", { name: "Change password" }));

    expect(screen.getByText("Passwords must match.")).toBeTruthy();
    expect(changeOwnPasswordMock).not.toHaveBeenCalled();
  });

  it("shows a failed current-password verification without clearing inputs", async () => {
    changeOwnPasswordMock.mockRejectedValue(new Error("Current password is incorrect."));
    render(<PasswordChangePanel user={user} compact />);
    fireEvent.click(screen.getByRole("button", { name: "Change password" }));
    fireEvent.change(screen.getByLabelText("Current password"), { target: { value: "wrong-pass" } });
    fireEvent.change(screen.getByLabelText("New password"), { target: { value: "new-password" } });
    fireEvent.change(screen.getByLabelText("Confirm new password"), { target: { value: "new-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Change password" }));

    expect(await screen.findByText("Current password is incorrect.")).toBeTruthy();
    expect(screen.getByLabelText("Current password")).toHaveValue("wrong-pass");
  });
});
