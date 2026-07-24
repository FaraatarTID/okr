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
      const payload = await bffLogin({
        username: username.trim(),
        password,
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
      <section
        className="panel"
        style={{
          marginBottom: "0.9rem",
          padding: "1.1rem 1.05rem",
          background:
            "linear-gradient(118deg, color-mix(in srgb, var(--surface) 94%, var(--accent) 6%), var(--surface))",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "0.7rem" }}>
          <img
            src="/okr-logo.webp"
            alt="OKR logo"
            width={42}
            height={74}
            style={{ display: "block", width: "42px", height: "74px", objectFit: "contain" }}
          />
          <h1 style={{ margin: 0 }}>OKR</h1>
        </div>
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
            <div style={{ display: "flex", alignItems: "center", gap: "0.7rem" }}>
              <img
                src="/okr-logo.webp"
                alt="OKR logo"
                width={34}
                height={60}
                style={{ display: "block", width: "34px", height: "60px", objectFit: "contain" }}
              />
              <h1 style={{ margin: 0 }}>OKR</h1>
            </div>
          </section>
        </main>
      }
    >
      <LoginPageContent />
    </Suspense>
  );
}
