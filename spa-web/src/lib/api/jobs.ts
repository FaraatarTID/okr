import { jsonHeaders, responseDetail } from "@/lib/api/http";
import type { BackendJobView } from "@/lib/api/backend-schema";

/**
 * Job view backed by the generated OpenAPI schema (components["schemas"]
 * ["JobView"]). Regenerate via `npm run gen:api` after backend schema changes.
 */
export type AsyncJobView = BackendJobView;

export async function submitBackendJob(input: {
  actor_username: string;
  kind: "pdf.weekly" | "ai.generate_json";
  payload: Record<string, unknown>;
  max_attempts?: number;
}): Promise<AsyncJobView> {
  const response = await fetch("/api/backend/v1/jobs", {
    method: "POST",
    headers: jsonHeaders(input.actor_username),
    body: JSON.stringify({
      actor_username: input.actor_username,
      kind: input.kind,
      payload: input.payload,
      max_attempts: input.max_attempts ?? 2,
    }),
  });
  if (!response.ok) {
    throw new Error(`Job submit failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as AsyncJobView;
}

export async function readBackendJob(input: {
  actor_username: string;
  job_id: string;
}): Promise<AsyncJobView> {
  const response = await fetch(`/api/backend/v1/jobs/${encodeURIComponent(input.job_id)}`, {
    method: "GET",
    cache: "no-store",
    headers: jsonHeaders(input.actor_username),
  });
  if (!response.ok) {
    throw new Error(`Job read failed: ${await responseDetail(response)}`);
  }
  return (await response.json()) as AsyncJobView;
}
