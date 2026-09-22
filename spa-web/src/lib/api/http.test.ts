import { describe, expect, it, vi } from "vitest";

import {
  backendBlobRequest,
  backendJsonRequest,
  backendNoContentRequest,
  jsonHeaders,
  retryWithFetch,
} from "@/lib/api/http";

function compileTimeOperationPathChecks(): void {
  void backendJsonRequest({
    operation: "api_submit_job_v1_jobs_post",
    path: "/v1/jobs",
    label: "valid typed path",
    body: { kind: "pdf.weekly", payload: {}, max_attempts: 2 },
  });
  void backendJsonRequest({
    // @ts-expect-error This documented backend operation is not BFF-public.
    operation: "api_admin_observability_metrics_v1_admin_observability_metrics_get",
    path: "/v1/admin/observability/metrics" as never,
    label: "non-public operation",
  });
  void backendNoContentRequest({
    operation: "api_delete_job_v1_jobs__job_id__delete",
    path: "/v1/jobs/job-1",
    label: "valid no-content operation",
  });
  void backendBlobRequest({
    operation: "api_admin_db_backup_v1_admin_db_backup_get",
    path: "/v1/admin/db-backup",
    label: "valid binary download",
  });
  void backendBlobRequest({
    // @ts-expect-error JSON operations cannot use the binary download helper.
    operation: "api_admin_ai_health_v1_admin_ai_health_get",
    path: "/v1/admin/ai-health" as never,
    label: "invalid binary download",
  });
  void backendJsonRequest({
    // @ts-expect-error A 204 response must use backendNoContentRequest.
    operation: "api_delete_job_v1_jobs__job_id__delete",
    path: "/v1/jobs/job-1" as never,
    label: "invalid JSON operation",
  });
  // @ts-expect-error Job submission has an OpenAPI-required request body.
  void backendJsonRequest({
    operation: "api_submit_job_v1_jobs_post",
    path: "/v1/jobs",
    label: "missing required body",
  });
  void backendJsonRequest({
    operation: "api_submit_job_v1_jobs_post",
    // @ts-expect-error Job submission cannot be paired with the teams route.
    path: "/v1/teams",
    label: "invalid typed path",
    body: { kind: "pdf.weekly", payload: {}, max_attempts: 2 },
  });
}

void compileTimeOperationPathChecks;

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

describe("backendJsonRequest", () => {
  const originalFetch = globalThis.fetch;

  it("forwards a generated-operation request through the backend boundary", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: "job-1" }), { status: 200 }),
    );
    globalThis.fetch = fetchMock;
    const job = await backendJsonRequest({
      operation: "api_submit_job_v1_jobs_post",
      path: "/v1/jobs",
      actor: "alice",
      label: "Job submit",
      body: { actor_username: "alice", kind: "pdf.weekly", payload: {}, max_attempts: 2 },
    });
    expect(job.id).toBe("job-1");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/backend/v1/jobs",
      expect.objectContaining({ method: "POST" }),
    );
    globalThis.fetch = originalFetch;
  });

  it("serializes generated query parameters while preserving the operation method", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
    );
    globalThis.fetch = fetchMock;
    await backendJsonRequest({
      operation: "api_admin_ai_health_v1_admin_ai_health_get",
      path: "/v1/admin/ai-health",
      query: { live_probe: true },
      label: "AI health",
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/backend/v1/admin/ai-health?live_probe=true",
      expect.objectContaining({ method: "GET" }),
    );
    globalThis.fetch = originalFetch;
  });

  it("accepts a documented no-content response without parsing JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    globalThis.fetch = fetchMock;
    await expect(
      backendNoContentRequest({
        operation: "api_delete_job_v1_jobs__job_id__delete",
        path: "/v1/jobs/job-1",
        label: "Delete job",
      }),
    ).resolves.toBeUndefined();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/backend/v1/jobs/job-1",
      expect.objectContaining({ method: "DELETE" }),
    );
    globalThis.fetch = originalFetch;
  });
});

describe("backendBlobRequest", () => {
  const originalFetch = globalThis.fetch;

  it("only downloads the documented binary backup operation", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response("backup", {
        status: 200,
        headers: { "content-type": "application/octet-stream" },
      }),
    );
    globalThis.fetch = fetchMock;
    await expect(
      backendBlobRequest({
        operation: "api_admin_db_backup_v1_admin_db_backup_get",
        path: "/v1/admin/db-backup",
        label: "DB backup export",
      }),
    ).resolves.toBeInstanceOf(Blob);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/backend/v1/admin/db-backup",
      expect.objectContaining({ method: "GET" }),
    );
    globalThis.fetch = originalFetch;
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
