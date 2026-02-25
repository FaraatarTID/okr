"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { bffLogin } from "@/lib/api";
import { loadAuthUser, saveAuthUser } from "@/lib/auth-session";

function safeReturnPath(raw: string | null): string {
  const value = String(raw || "").trim();
  if (!value.startsWith("/") || value.startsWith("//")) {
    return "/";
  }
  return value;
}

function LoginPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  const returnTo = safeReturnPath(searchParams.get("return_to"));

  useEffect(() => {
    if (loadAuthUser()) {
      router.replace(returnTo);
    }
  }, [returnTo, router]);

  async function handleLogin(): Promise<void> {
    setPending(true);
    setError("");
    try {
      const payload = await bffLogin({
        username: username.trim(),
        password,
      });
      if (!payload.user) {
        setError(payload.detail || payload.error_code || "Login failed. Verify credentials.");
        return;
      }
      saveAuthUser(payload.user);
      router.replace(returnTo);
    } catch (loginError) {
      setError(String(loginError instanceof Error ? loginError.message : loginError));
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="page-shell">
      <section
        className="panel"
        style={{
          marginBottom: "0.9rem",
          padding: "1.1rem 1.05rem",
          background:
            "linear-gradient(118deg, color-mix(in srgb, var(--surface) 94%, var(--accent) 6%), var(--surface))",
        }}
      >
        <p className="kicker">Authentication</p>
        <h1 style={{ margin: "0.15rem 0 0.45rem" }}>Sign in to OKR Atlas SPA</h1>
        <p style={{ margin: 0, color: "var(--ink-soft)", maxWidth: "60ch" }}>
          Sign in to continue to your workspace.
        </p>
      </section>

      <section className="panel" style={{ padding: "0.95rem", maxWidth: 540 }}>
        <label htmlFor="username" style={{ fontSize: "0.85rem", color: "var(--ink-soft)" }}>
          Username
        </label>
        <input
          id="username"
          className="input"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          autoComplete="username"
          style={{ marginBottom: "0.55rem", marginTop: "0.22rem" }}
        />

        <label htmlFor="password" style={{ fontSize: "0.85rem", color: "var(--ink-soft)" }}>
          Password
        </label>
        <input
          id="password"
          className="input"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="current-password"
          style={{ marginBottom: "0.7rem", marginTop: "0.22rem" }}
        />

        <button
          className="primary-button"
          type="button"
          onClick={handleLogin}
          disabled={pending || !username.trim() || !password}
        >
          {pending ? "Signing in..." : "Sign in"}
        </button>

        {error ? <p style={{ margin: "0.65rem 0 0", color: "var(--error)" }}>{error}</p> : null}
      </section>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <main className="page-shell">
          <section className="panel" style={{ padding: "1rem", maxWidth: 540 }}>
            <p className="kicker">Authentication</p>
            <p style={{ margin: "0.2rem 0 0", color: "var(--ink-soft)" }}>Loading login page...</p>
          </section>
        </main>
      }
    >
      <LoginPageContent />
    </Suspense>
  );
}
