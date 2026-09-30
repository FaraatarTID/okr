"use client";

import { useEffect, useState } from "react";

import { readSessionUser, SessionAuthError, type AuthUser } from "@/lib/api";

const SESSION_REFRESH_MS = 60_000;

/**
 * True when two session payloads carry the same fields.
 *
 * The session is re-read every minute and on every tab focus. Roughly thirty
 * effects across the shell are keyed on the `user` object, so handing them a
 * fresh but identical object makes each one re-run: the snapshot reloads, the
 * "Loading..." indicators flash and the open panel refetches. Keeping the previous
 * reference when nothing changed makes the background check invisible.
 */
export function isSameSessionUser(a: AuthUser | null, b: AuthUser | null): boolean {
  if (a === b) {
    return true;
  }
  if (!a || !b) {
    return false;
  }
  const left = a as unknown as Record<string, unknown>;
  const right = b as unknown as Record<string, unknown>;
  const keys = new Set([...Object.keys(left), ...Object.keys(right)]);
  for (const key of keys) {
    if (left[key] !== right[key]) {
      return false;
    }
  }
  return true;
}

export default function useAuthBootstrap() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [authHydrated, setAuthHydrated] = useState(false);

  useEffect(() => {
    let active = true;
    let inFlight = false;
    let lastForegroundCheck = -Infinity;
    const refresh = async () => {
      if (!active || inFlight) {
        return;
      }
      inFlight = true;
      try {
        const sessionUser = await readSessionUser();
        if (!active) {
          return;
        }
        setUser((previous) => (isSameSessionUser(previous, sessionUser) ? previous : sessionUser));
        setAuthHydrated(true);
      } catch (error) {
        if (!active) {
          return;
        }
        if (error instanceof SessionAuthError) {
          setUser(null);
          setAuthHydrated(true);
        }
      } finally {
        inFlight = false;
      }
    };
    const onForeground = () => {
      if (document.visibilityState !== "visible") {
        return;
      }
      const now = Date.now();
      if (now - lastForegroundCheck < 1_000) {
        return;
      }
      lastForegroundCheck = now;
      void refresh();
    };
    void refresh();
    const interval = window.setInterval(() => {
      if (document.visibilityState === "visible") {
        void refresh();
      }
    }, SESSION_REFRESH_MS);
    document.addEventListener("visibilitychange", onForeground);
    window.addEventListener("focus", onForeground);
    return () => {
      active = false;
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", onForeground);
      window.removeEventListener("focus", onForeground);
    };
  }, []);

  return {
    user,
    setUser,
    authHydrated,
  };
}
