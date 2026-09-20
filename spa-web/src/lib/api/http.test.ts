import { describe, expect, it, vi } from "vitest";

import { jsonHeaders, retryWithFetch } from "@/lib/api/http";

describe("jsonHeaders", () => {
  it("omits JSON content type when includeJsonContentType is false", () => {
    expect(jsonHeaders("admin", false)).toEqual({
      "x-okr-actor": "admin",
    });
  });

  it("includes JSON content type by default", () => {
    expect(jsonHeaders("admin")).toEqual({
      "content-type": "application/json",
      "x-okr-actor": "admin",
    });
  });
});

// `perAttemptTimeoutMs` was declared on `RetryWithFetchOptions` and never read,
// so the helper advertised a deadline it did not enforce. These tests exist so
// that cannot come back silently: they fail if the abort is dropped.
describe("retryWithFetch per-attempt timeout", () => {
  it("aborts the attempt when the deadline elapses", async () => {
    const signals: AbortSignal[] = [];
    await expect(
      retryWithFetch(
        (signal) => {
          signals.push(signal);
          return new Promise<Response>((_resolve, reject) => {
            signal.addEventListener("abort", () =>
              reject(new DOMException("This operation was aborted", "AbortError")),
            );
          });
        },
        async () => "unreachable",
        { label: "probe", perAttemptTimeoutMs: 40, maxAttempts: 1 },
      ),
    ).rejects.toThrow(/probe failed: .*This operation was aborted/);
    expect(signals).toHaveLength(1);
    expect(signals[0]?.aborted).toBe(true);
  });

  it("hands a live signal to the fetch and clears the deadline on success", async () => {
    let captured: AbortSignal | undefined;
    const result = await retryWithFetch(
      async (signal) => {
        captured = signal;
        return new Response("{}", { status: 200 });
      },
      async () => "ok",
      { label: "probe", perAttemptTimeoutMs: 50, maxAttempts: 1 },
    );
    expect(result).toBe("ok");
    expect(typeof captured?.addEventListener).toBe("function");
    expect(captured?.aborted).toBe(false);
  });

  it("does not abort the signal of an attempt that already settled", async () => {
    let captured: AbortSignal | undefined;
    await retryWithFetch(
      async (signal) => {
        captured = signal;
        return new Response("{}", { status: 200 });
      },
      async () => "ok",
      { label: "probe", perAttemptTimeoutMs: 20, maxAttempts: 1 },
    );
    await new Promise((resolve) => setTimeout(resolve, 60));
    expect(captured?.aborted).toBe(false);
  });

  it("treats a deadline abort as transient and spends the remaining attempts", async () => {
    // A real abort rejects with AbortError and a message containing "aborted",
    // which isTransientNetworkError classifies as retryable. Probed against the
    // runtime rather than assumed: name=AbortError, message="This operation was
    // aborted". This test pins that behaviour so that changing it is a
    // deliberate act, and so the worst-case wall time stays understood.
    const fetchFn = vi.fn(
      (signal: AbortSignal) =>
        new Promise<Response>((_resolve, reject) => {
          signal.addEventListener("abort", () =>
            reject(new DOMException("This operation was aborted", "AbortError")),
          );
        }),
    );
    await expect(
      retryWithFetch(fetchFn, async () => "unreachable", {
        label: "probe",
        perAttemptTimeoutMs: 20,
        maxAttempts: 3,
        baseDelayMs: 1,
      }),
    ).rejects.toThrow(/probe failed/);
    expect(fetchFn).toHaveBeenCalledTimes(3);
  });

  it("gives each attempt its own signal and still retries transient failures", async () => {
    const signals: AbortSignal[] = [];
    let attempt = 0;
    const result = await retryWithFetch(
      async (signal) => {
        signals.push(signal);
        attempt += 1;
        if (attempt === 1) {
          throw new Error("socket hang up");
        }
        return new Response("{}", { status: 200 });
      },
      async () => "recovered",
      { label: "probe", perAttemptTimeoutMs: 1_000, maxAttempts: 3, baseDelayMs: 1 },
    );
    expect(result).toBe("recovered");
    expect(signals).toHaveLength(2);
    expect(signals[0]).not.toBe(signals[1]);
  });
});
