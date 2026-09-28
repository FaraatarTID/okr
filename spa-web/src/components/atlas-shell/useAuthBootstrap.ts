"use client";

import { useEffect, useState } from "react";

import { readSessionUser, SessionAuthError, type AuthUser } from "@/lib/api";

const SESSION_REFRESH_MS = 60_000;

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
        setUser(sessionUser);
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
