"use client";

import { readBackendJob, type AuthUser, type AsyncJobView } from "@/lib/api";

type WaitForJobOptions = {
  timeoutMs?: number;
  initialPollIntervalMs?: number;
  maxPollIntervalMs?: number;
  signal?: AbortSignal;
};

export async function waitForBackendJobResult(
  activeUser: AuthUser,
  jobId: string,
  options?: WaitForJobOptions,
): Promise<AsyncJobView> {
  const {
    timeoutMs = 300_000,
    initialPollIntervalMs = 1_000,
    maxPollIntervalMs = 10_000,
    signal,
  } = options ?? {};

  const started = Date.now();
  let pollInterval = initialPollIntervalMs;

  while (Date.now() - started < timeoutMs) {
    if (signal?.aborted) {
      throw new DOMException("Aborted", "AbortError");
    }

    const state = await readBackendJob({
      actor_username: activeUser.username,
      job_id: jobId,
    });
    const status = String(state.status || "").toLowerCase();
    if (status === "succeeded" || status === "failed" || status === "cancelled") {
      return state;
    }

    const jitter = Math.random() * pollInterval * 0.2;
    const delay = Math.min(pollInterval + jitter, maxPollIntervalMs);
    await new Promise<void>((resolve, reject) => {
      const timerId = window.setTimeout(resolve, delay);
      signal?.addEventListener(
        "abort",
        () => {
          window.clearTimeout(timerId);
          reject(new DOMException("Aborted", "AbortError"));
        },
        { once: true },
      );
    });

    pollInterval = Math.min(pollInterval * 2, maxPollIntervalMs);
  }
  throw new Error("Timed out waiting for backend job result.");
}
