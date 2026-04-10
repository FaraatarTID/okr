"use client";

import { useCallback, useEffect, useState } from "react";

import type { AtlasSnapshotResponse } from "@/lib/atlas";
import { readAtlasSnapshot, type AuthUser } from "@/lib/api";

type UseSnapshotLifecycleInput = {
  user: AuthUser | null;
  mode: string;
  parsedCycleId: number | null;
  ownerIds: number[] | undefined;
  ownerIdsError: string;
  rolloutAllowed: boolean;
};

export default function useSnapshotLifecycle({
  user,
  mode,
  parsedCycleId,
  ownerIds,
  ownerIdsError,
  rolloutAllowed,
}: UseSnapshotLifecycleInput) {
  const [snapshotPending, setSnapshotPending] = useState(false);
  const [snapshotError, setSnapshotError] = useState("");
  const [snapshotPayload, setSnapshotPayload] = useState<AtlasSnapshotResponse | null>(null);

  const clearSnapshot = useCallback(() => {
    setSnapshotPayload(null);
  }, []);

  const loadSnapshotForUser = useCallback(
    async (activeUser: AuthUser): Promise<void> => {
      if (!parsedCycleId || ownerIdsError) {
        return;
      }
      const payload = await readAtlasSnapshot({
        actor_username: activeUser.username,
        cycle_id: parsedCycleId,
        include_analysis: true,
        owner_ids: ownerIds,
      });
      setSnapshotPayload(payload);
    },
    [ownerIds, ownerIdsError, parsedCycleId],
  );

  useEffect(() => {
    if (!user || !parsedCycleId || ownerIdsError || !rolloutAllowed) {
      if (!parsedCycleId || ownerIdsError || !rolloutAllowed) {
        setSnapshotPayload(null);
      }
      setSnapshotPending(false);
      return;
    }

    let active = true;
    setSnapshotPending(true);
    setSnapshotError("");

    const timer = window.setTimeout(() => {
      void (async () => {
        try {
          await loadSnapshotForUser(user);
        } catch (error) {
          if (!active) {
            return;
          }
          setSnapshotError(String(error instanceof Error ? error.message : error));
          setSnapshotPayload(null);
        } finally {
          if (active) {
            setSnapshotPending(false);
          }
        }
      })();
    }, 200);

    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [loadSnapshotForUser, ownerIds, ownerIdsError, parsedCycleId, rolloutAllowed, user]);

  useEffect(() => {
    if (!user || mode !== "atlas" || !parsedCycleId || ownerIdsError || !rolloutAllowed) {
      return;
    }

    let active = true;
    const pollTimer = window.setInterval(() => {
      void (async () => {
        try {
          await loadSnapshotForUser(user);
          if (active) {
            setSnapshotError("");
          }
        } catch (error) {
          if (!active) {
            return;
          }
          setSnapshotError(String(error instanceof Error ? error.message : error));
        }
      })();
    }, 45000);

    return () => {
      active = false;
      window.clearInterval(pollTimer);
    };
  }, [loadSnapshotForUser, mode, ownerIds, ownerIdsError, parsedCycleId, rolloutAllowed, user]);

  return {
    snapshotPending,
    snapshotError,
    snapshotPayload,
    clearSnapshot,
    loadSnapshotForUser,
  };
}
