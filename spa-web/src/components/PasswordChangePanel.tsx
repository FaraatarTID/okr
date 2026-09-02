"use client";

import { useState } from "react";

import { resetUserPasswordMutation } from "@/lib/api/admin";
import type { AuthUser } from "@/lib/api/auth";

export default function PasswordChangePanel({
  user,
  onComplete,
  compact = false,
}: {
  user: AuthUser;
  onComplete?: () => void;
  compact?: boolean;
}) {
  const [open, setOpen] = useState(!compact);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [pending, setPending] = useState(false);

  async function handleSubmit(): Promise<void> {
    setError("");
    setSuccess("");
    if (!newPassword || newPassword !== confirmPassword) {
      setError("Passwords must match.");
      return;
    }
    setPending(true);
    try {
      await resetUserPasswordMutation({
        actor_username: user.username,
        user_id: user.id,
        new_password: newPassword,
        require_change: false,
      });
      setNewPassword("");
      setConfirmPassword("");
      setSuccess("Password updated successfully.");
      onComplete?.();
    } catch (changeError) {
      setError(String(changeError instanceof Error ? changeError.message : changeError));
    } finally {
      setPending(false);
    }
  }

  if (!open) {
    return (
      <button className="secondary-button" type="button" onClick={() => setOpen(true)} style={{ width: "100%" }}>
        Change password
      </button>
    );
  }

  return (
    <section className={compact ? "panel" : "panel login-shell-card"}>
      <h2 style={{ marginTop: 0 }}>Change your password</h2>
      <p className="login-feedback">Choose a new password for your account.</p>
      <label htmlFor="new-password" className="login-label">New password</label>
      <input
        id="new-password"
        className="input login-field"
        type="password"
        value={newPassword}
        onChange={(event) => setNewPassword(event.target.value)}
        autoComplete="new-password"
      />
      <label htmlFor="confirm-password" className="login-label">Confirm new password</label>
      <input
        id="confirm-password"
        className="input login-field"
        type="password"
        value={confirmPassword}
        onChange={(event) => setConfirmPassword(event.target.value)}
        autoComplete="new-password"
      />
      <button
        className="primary-button"
        type="button"
        onClick={handleSubmit}
        disabled={pending || !newPassword || !confirmPassword}
      >
        {pending ? "Updating..." : "Set new password"}
      </button>
      {error ? <p className="login-feedback">{error}</p> : null}
      {success ? <p role="status" className="login-feedback">{success}</p> : null}
    </section>
  );
}
