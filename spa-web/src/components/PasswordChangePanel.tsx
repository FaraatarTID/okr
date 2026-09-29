"use client";

import { useState } from "react";

import { changeOwnPassword, type AuthUser } from "@/lib/api/auth";

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
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [pending, setPending] = useState(false);

  async function handleSubmit(): Promise<void> {
    setError("");
    setSuccess("");
    if (!currentPassword) {
      setError("Enter your current password.");
      return;
    }
    if (!newPassword || newPassword !== confirmPassword) {
      setError("Passwords must match.");
      return;
    }
    setPending(true);
    try {
      await changeOwnPassword({
        username: user.username,
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword("");
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
      <p className="login-feedback">Verify your current password, then choose a new one.</p>
      <label htmlFor="current-password" className="login-label">Current password</label>
      <input
        id="current-password"
        className="input login-field"
        type="password"
        value={currentPassword}
        onChange={(event) => setCurrentPassword(event.target.value)}
        autoComplete="current-password"
      />
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
        disabled={pending || !currentPassword || !newPassword || !confirmPassword}
      >
        {pending ? "Updating..." : "Change password"}
      </button>
      {error ? <p className="login-feedback">{error}</p> : null}
      {success ? <p role="status" className="login-feedback">{success}</p> : null}
    </section>
  );
}
