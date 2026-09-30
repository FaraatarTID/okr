"use client";

import PasswordChangePanel from "@/components/PasswordChangePanel";
import type { AuthUser } from "@/lib/api/auth";

/**
 * The signed-in card at the bottom of the sidebar.
 *
 * Admins do not get the change-password control here: the admin panel lists every
 * user, the admin included, with its own password action. Everyone else has no
 * admin panel, so this is the only place they can change their own password.
 */
export default function SidebarAccountCard({
  user,
  isAdmin,
  onSignOut,
}: {
  user: AuthUser;
  isAdmin: boolean;
  onSignOut: () => void;
}) {
  return (
    <div
      style={{
        marginTop: "0.8rem",
        border: "1px solid var(--line)",
        borderRadius: 10,
        padding: "0.55rem 0.58rem",
        background: "var(--surface-alt)",
      }}
    >
      <div style={{ fontSize: "0.82rem", color: "var(--ink-soft)" }}>Signed in as</div>
      <strong style={{ display: "block", marginTop: "0.2rem" }}>{user.display_name}</strong>
      {isAdmin ? null : <PasswordChangePanel user={user} compact />}
      <button
        className="primary-button"
        type="button"
        onClick={onSignOut}
        style={{ marginTop: "0.55rem", width: "100%" }}
      >
        Sign out
      </button>
    </div>
  );
}