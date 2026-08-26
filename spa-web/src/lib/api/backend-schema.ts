/**
 * Typed access to backend OpenAPI schema types.
 *
 * Generated from `src/lib/api/openapi.json` (exported by
 * `scripts/export_openapi.py`). Regenerate with `npm run gen:api`.
 * CI fails when the committed artifact drifts from the live schema.
 */
import type { components } from "./generated/schema";

export type BackendSchemas = components["schemas"];

/** Serialized async job returned by /v1/jobs endpoints. */
export type BackendJobView = BackendSchemas["JobView"];

/** Healthz payload including data-access mode and dead-job count. */
export type BackendHealthz = {
  status?: string;
  data_access_mode?: string;
  configured_mode?: string;
  dead_jobs?: number | null;
};

/**
 * Parse a healthz response body into a typed shape.
 * Unknown shapes return null so callers can fail closed.
 */
export function parseHealthz(body: unknown): BackendHealthz | null {
  if (typeof body !== "object" || body === null) {
    return null;
  }
  const record = body as Record<string, unknown>;
  const deadJobsRaw = record.dead_jobs;
  return {
    status: typeof record.status === "string" ? record.status : undefined,
    data_access_mode:
      typeof record.data_access_mode === "string"
        ? record.data_access_mode
        : undefined,
    configured_mode:
      typeof record.configured_mode === "string"
        ? record.configured_mode
        : undefined,
    dead_jobs:
      typeof deadJobsRaw === "number"
        ? deadJobsRaw
        : deadJobsRaw === null
          ? null
          : undefined,
  };
}
