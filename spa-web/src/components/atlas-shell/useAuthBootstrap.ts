"use client";

import { useEffect, useState } from "react";

import { readSessionUser, readSpaRolloutConfig, type AuthUser } from "@/lib/api";
import type { SpaRolloutConfig } from "@/lib/rollout";

export default function useAuthBootstrap() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [authHydrated, setAuthHydrated] = useState(false);
  const [rolloutConfig, setRolloutConfig] = useState<SpaRolloutConfig | null>(null);

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

  useEffect(() => {
    let active = true;

    void (async () => {
      try {
        const config = await readSpaRolloutConfig();
        if (!active) {
          return;
        }
        setRolloutConfig(config);
      } catch {
        if (!active) {
          return;
        }
        setRolloutConfig(null);
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
    rolloutConfig,
  };
}
