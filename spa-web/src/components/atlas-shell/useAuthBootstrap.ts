"use client";

import { useEffect, useState } from "react";

import { readSessionUser, type AuthUser } from "@/lib/api";

export default function useAuthBootstrap() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [authHydrated, setAuthHydrated] = useState(false);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const sessionUser = await readSessionUser();
        if (!active) {
          return;
        }
        setUser(sessionUser);
      } catch {
        if (!active) {
          return;
        }
        setUser(null);
      } finally {
        if (active) {
          setAuthHydrated(true);
        }
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  return {
    user,
    setUser,
    authHydrated,
  };
}
