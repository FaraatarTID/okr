"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import type { AtlasSnapshotResponse } from "@/lib/atlas";
import { readAtlasSnapshot, type AuthUser } from "@/lib/api";

type UseSnapshotLifecycleInput = {
  user: AuthUser | null;
  mode: string;
  parsedCycleId: number | null;
  ownerIds: number[] | undefined;
  ownerIdsError: string;
};

function resolveSnapshotPollIntervalMs(): number {
  const mode = String(process.env.NEXT_PUBLIC_OKR_DATA_ACCESS_MODE || "").trim().toLowerCase();
  if (mode === "supabase_api" || mode === "supabase-http" || mode === "supabase_https") {
    return 600_000;
  }
  return 45_000;
}

export default function useSnapshotLifecycle({
  user,
  mode,
  parsedCycleId,
  ownerIds,
  ownerIdsError,
}: UseSnapshotLifecycleInput) {
  const snapshotPollIntervalMs = resolveSnapshotPollIntervalMs();
  const [snapshotPending, setSnapshotPending] = useState(false);
  const [snapshotError, setSnapshotError] = useState("");
  const [snapshotPayload, setSnapshotPayload] = useState<AtlasSnapshotResponse | null>(null);
  const snapshotRequestIdRef = useRef(0);

  const clearSnapshot = useCallback(() => {
    setSnapshotPayload(null);
  }, []);

  const loadSnapshotForUser = useCallback(
    async (activeUser: AuthUser): Promise<void> => {
      if (!parsedCycleId || ownerIdsError) {
        return;
      }
      const requestId = snapshotRequestIdRef.current + 1;
      snapshotRequestIdRef.current = requestId;
      const payload = await readAtlasSnapshot({
        actor_username: activeUser.username,
        cycle_id: parsedCycleId,
        // Raw AI analysis is only needed by the Atlas inspector. Keeping it
        // out of dashboard/timeline/weekly payloads avoids serializing and
        // transferring large JSON blobs on every navigation.
        include_analysis: mode === "atlas",
        owner_ids: ownerIds,
      });
      if (snapshotRequestIdRef.current === requestId) {
        setSnapshotPayload(payload);
      }
    },
    [ownerIds, ownerIdsError, parsedCycleId],
  );

  useEffect(() => {
    if (!user || !parsedCycleId || ownerIdsError) {
      if (!parsedCycleId || ownerIdsError) {
        setSnapshotPayload(null);
      }
      setSnapshotPending(false);
      return;
    }

    let active = true;
    snapshotRequestIdRef.current += 1;
    setSnapshotPending(true);
    setSnapshotError("");
    const bootstrapGeneration = snapshotRequestIdRef.current;

    // Yield one event-loop turn so callers can explicitly trigger a load
    // during the same render cycle without racing the automatic bootstrap.
    // This replaces the former 200 ms delay without adding user-visible wait.
    const bootstrapTimer = window.setTimeout(() => {
      if (!active || snapshotRequestIdRef.current !== bootstrapGeneration) {
        return;
      }
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
    }, 0);

    return () => {
      active = false;
      snapshotRequestIdRef.current += 1;
      window.clearTimeout(bootstrapTimer);
    };
  }, [loadSnapshotForUser, ownerIds, ownerIdsError, parsedCycleId, user]);

  useEffect(() => {
    if (!user || mode !== "atlas" || !parsedCycleId || ownerIdsError) {
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
    }, snapshotPollIntervalMs);

    return () => {
      active = false;
      window.clearInterval(pollTimer);
    };
  }, [loadSnapshotForUser, mode, ownerIds, ownerIdsError, parsedCycleId, snapshotPollIntervalMs, user]);

  return {
    snapshotPending,
    snapshotError,
    snapshotPayload,
    snapshotPollIntervalMs,
    clearSnapshot,
    loadSnapshotForUser,
  };
}
