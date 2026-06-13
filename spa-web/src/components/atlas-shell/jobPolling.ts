"use client";

import { readBackendJob, type AuthUser, type AsyncJobView } from "@/lib/api";

export async function waitForBackendJobResult(
  activeUser: AuthUser,
  jobId: string,
  timeoutMs = 300_000,
  pollIntervalMs = 1_000,
): Promise<AsyncJobView> {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const state = await readBackendJob({
      actor_username: activeUser.username,
      job_id: jobId,
    });
    const status = String(state.status || "").toLowerCase();
    if (status === "succeeded" || status === "failed" || status === "cancelled") {
      return state;
    }
    await new Promise((resolve) => window.setTimeout(resolve, pollIntervalMs));
  }
  throw new Error("Timed out waiting for backend job result.");
}
