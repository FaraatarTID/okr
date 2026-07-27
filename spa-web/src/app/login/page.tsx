"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { bffLogin, readSessionUser } from "@/lib/api";

const SAFE_RETURN_PATHS = new Set([
  "/",
  "/dashboard",
  "/admin",
  "/check-in",
  "/daily",
  "/weekly",
  "/timeline",
  "/ritual",
  "/retrobox",
]);

function safeReturnPath(raw: string | null): string {
  const value = String(raw || "").trim();
  if (!value.startsWith("/") || value.startsWith("//")) {
    return "/";
  }
  // Only allow paths that match our known routes
  const path = value.split("?")[0].split("#")[0];
  if (SAFE_RETURN_PATHS.has(path)) {
    return value;
  }
  return "/";
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
    let active = true;
    void (async () => {
      try {
        await readSessionUser();
        if (!active) {
          return;
        }
        router.replace(returnTo);
      } catch {
        // no active session; keep login view
      }
    })();
    return () => {
      active = false;
    };
  }, [returnTo, router]);

  async function handleLogin(): Promise<void> {
    setPending(true);
    setError("");
    try {
      const usernameFromDom = (document.getElementById("username") as HTMLInputElement | null)
        ?.value?.trim();
      const passwordFromDom = (document.getElementById("password") as HTMLInputElement | null)
        ?.value ?? "";
      const payload = await bffLogin({
        username: usernameFromDom || username.trim(),
        password: passwordFromDom || password,
      });
      if (!payload.user) {
        setError(payload.detail || payload.error_code || "Login failed. Verify credentials.");
        return;
      }
      router.replace(returnTo);
    } catch (loginError) {
      setError(String(loginError instanceof Error ? loginError.message : loginError));
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="page-shell">
      <section className="panel login-shell-hero">
        <div className="login-brand-row">
          <img src="/okr-logo.webp" alt="OKR logo" width={42} height={74} className="login-logo" />
          <h1 className="login-brand-title">OKR</h1>
        </div>
      </section>

      <section className="panel login-shell-card">
        <label htmlFor="username" className="login-label">
          Username
        </label>
        <input
          id="username"
          className="input login-field"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          autoComplete="username"
        />

        <label htmlFor="password" className="login-label">
          Password
        </label>
        <input
          id="password"
          className="input login-field"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="current-password"
        />

        <button
          className="primary-button"
          type="button"
          onClick={handleLogin}
          disabled={pending || !username.trim() || !password}
        >
          {pending ? "Signing in..." : "Sign in"}
        </button>

        {error ? <p className="login-feedback">{error}</p> : null}
      </section>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <main className="page-shell">
          <section className="panel login-shell-hero">
            <div className="login-brand-row">
              <img src="/okr-logo.webp" alt="OKR logo" width={34} height={60} className="login-logo login-logo--mini" />
              <h1 className="login-brand-title">OKR</h1>
            </div>
          </section>
        </main>
      }
    >
      <LoginPageContent />
    </Suspense>
  );
}
